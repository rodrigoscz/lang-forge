from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.db.schema import Database


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ApiCache:
    def __init__(self, database: Database, ttl_hours: int = 24) -> None:
        if ttl_hours < 1:
            raise ValueError("ttl_hours must be at least 1")
        self.database = database
        self.ttl = timedelta(hours=ttl_hours)

    def make_key(self, endpoint: str, params: dict[str, Any]) -> str:
        payload = json.dumps({"endpoint": endpoint, "params": params}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        cache_key = self.make_key(endpoint, params)
        now = _utc_now().isoformat()
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT response_json
                FROM api_cache
                WHERE cache_key = ? AND expires_at > ?
                """,
                (cache_key, now),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["response_json"])

    def set(
        self,
        endpoint: str,
        params: dict[str, Any],
        response: dict[str, Any],
        *,
        experiment_id: str | None = None,
    ) -> None:
        cache_key = self.make_key(endpoint, params)
        expires_at = (_utc_now() + self.ttl).isoformat()
        params_json = json.dumps(params, sort_keys=True)
        response_json = json.dumps(response, sort_keys=True)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO api_cache (cache_key, experiment_id, endpoint, params_json, response_json, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                  experiment_id = excluded.experiment_id,
                  endpoint = excluded.endpoint,
                  params_json = excluded.params_json,
                  response_json = excluded.response_json,
                  expires_at = excluded.expires_at,
                  created_at = datetime('now')
                """,
                (cache_key, experiment_id, endpoint, params_json, response_json, expires_at),
            )

    def invalidate(
        self,
        *,
        endpoint: str | None = None,
        params: dict[str, Any] | None = None,
        experiment_id: str | None = None,
    ) -> int:
        with self.database.connect() as connection:
            if endpoint is not None and params is not None:
                cursor = connection.execute("DELETE FROM api_cache WHERE cache_key = ?", (self.make_key(endpoint, params),))
            elif experiment_id is not None:
                cursor = connection.execute("DELETE FROM api_cache WHERE experiment_id = ?", (experiment_id,))
            elif endpoint is not None:
                cursor = connection.execute("DELETE FROM api_cache WHERE endpoint = ?", (endpoint,))
            else:
                cursor = connection.execute("DELETE FROM api_cache")
            return cursor.rowcount
