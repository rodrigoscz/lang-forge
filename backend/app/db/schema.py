from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_URL = "sqlite:///data/experiments.db"


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        with self.connect() as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))
            self._migrate_existing(connection)

    def _migrate_existing(self, connection: sqlite3.Connection) -> None:
        api_cache_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(api_cache)").fetchall()
        }
        if "experiment_id" not in api_cache_columns:
            connection.execute("ALTER TABLE api_cache ADD COLUMN experiment_id TEXT")


def database_from_env() -> Database:
    return Database(path=_path_from_database_url(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)))


def _path_from_database_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme and parsed.scheme != "sqlite":
        raise ValueError("DATABASE_URL must use sqlite://")

    if parsed.scheme == "sqlite":
        raw_path = parsed.path
        if parsed.netloc:
            raw_path = f"/{parsed.netloc}{parsed.path}"
    else:
        raw_path = database_url

    path = Path(raw_path.lstrip("/")) if raw_path.startswith("/") and not raw_path.startswith("//") else Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path
