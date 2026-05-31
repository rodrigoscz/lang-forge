from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import OrderedDict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.dataforseo.budget import QueryBudget
from app.dataforseo.cache import ApiCache
from app.dataforseo.rate_limit import AsyncRateLimiter


logger = logging.getLogger(__name__)


class DataforSEOError(RuntimeError):
    pass


class DataforSEOConfigError(DataforSEOError):
    pass


class DataforSEOAPIError(DataforSEOError):
    pass


class DataforSEOConfig(BaseModel):
    login: str = Field(min_length=1)
    password: str = Field(min_length=1)
    base_url: str = "https://api.dataforseo.com/v3"
    rate_limit_rps: int = 5
    monthly_budget_cents: int = 10_000
    per_experiment_limit: int = 500
    default_location_code: int = 2840
    default_language_code: str = "en"
    default_cost_cents: int = 2

    @classmethod
    def from_env(cls) -> "DataforSEOConfig":
        login = os.getenv("DATAFORSEO_LOGIN")
        password = os.getenv("DATAFORSEO_PASSWORD")
        if not login or not password:
            raise DataforSEOConfigError(
                "Missing DataforSEO credentials. Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD in the environment."
            )
        return cls(
            login=login,
            password=password,
            base_url=os.getenv("DATAFORSEO_BASE_URL", "https://api.dataforseo.com/v3"),
            rate_limit_rps=int(os.getenv("DATAFORSEO_RATE_LIMIT_RPS", "5")),
            monthly_budget_cents=int(os.getenv("MONTHLY_BUDGET_CENTS", "10000")),
            per_experiment_limit=int(os.getenv("EXPERIMENT_QUERY_LIMIT", "500")),
            default_cost_cents=int(os.getenv("DATAFORSEO_QUERY_COST_CENTS", "2")),
        )


class SERPResponse(BaseModel):
    keyword: str
    location_code: int
    language_code: str
    ai_overview: dict[str, Any] | None = None
    citations: list[str] = Field(default_factory=list)
    raw: dict[str, Any]
    timestamp: datetime
    estimated_cost: Decimal
    from_cache: bool = False


class DataforSEOClient:
    def __init__(
        self,
        config: DataforSEOConfig,
        *,
        cache: ApiCache | None = None,
        budget: QueryBudget | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.cache = cache
        self.budget = budget
        self.rate_limiter = rate_limiter or AsyncRateLimiter(config.rate_limit_rps)
        self._http_client = http_client
        self._locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._max_locks = 1000
        self._eviction_lock = asyncio.Lock()
        self._budget_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._max_budget_locks = 100
        self._budget_eviction_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()

    async def query_serp(
        self,
        *,
        keyword: str,
        experiment_id: str,
        location_code: int | None = None,
        language_code: str | None = None,
        device: Literal["desktop", "mobile"] = "desktop",
        force_fresh: bool = False,
        control_query: bool = False,
    ) -> SERPResponse:
        endpoint = "/serp/google/organic/live/advanced"
        params = {
            "keyword": keyword,
            "location_code": location_code or self.config.default_location_code,
            "language_code": language_code or self.config.default_language_code,
            "device": device,
        }
        raw = await self._execute_query(
            endpoint=endpoint,
            params=params,
            experiment_id=experiment_id,
            force_fresh=force_fresh or control_query,
        )
        return self._to_serp_response(raw, params=params, from_cache=raw.get("_from_cache", False))

    async def query_ai_overview(
        self,
        *,
        keyword: str,
        experiment_id: str,
        location_code: int | None = None,
        language_code: str | None = None,
        force_fresh: bool = False,
        control_query: bool = False,
    ) -> SERPResponse:
        endpoint = "/serp/google/ai_overview/live/advanced"
        params = {
            "keyword": keyword,
            "location_code": location_code or self.config.default_location_code,
            "language_code": language_code or self.config.default_language_code,
        }
        raw = await self._execute_query(
            endpoint=endpoint,
            params=params,
            experiment_id=experiment_id,
            force_fresh=force_fresh or control_query,
        )
        return self._to_serp_response(raw, params=params, from_cache=raw.get("_from_cache", False))

    async def _execute_query(
        self,
        *,
        endpoint: str,
        params: dict[str, Any],
        experiment_id: str,
        force_fresh: bool,
    ) -> dict[str, Any]:
        key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        if key not in self._locks:
            async with self._eviction_lock:
                if key not in self._locks:
                    if len(self._locks) >= self._max_locks:
                        evicted = False
                        for old_key in list(self._locks.keys()):
                            if not self._locks[old_key].locked():
                                self._locks.pop(old_key, None)
                                evicted = True
                                break
                        if not evicted:
                            oldest_key = next(iter(self._locks))
                            await self._locks[oldest_key].acquire()
                            self._locks.pop(oldest_key, None)
                    self._locks[key] = asyncio.Lock()
                self._locks.move_to_end(key)
        else:
            self._locks.move_to_end(key)
        async with self._locks[key]:
            if self.cache is not None and not force_fresh:
                cached = await asyncio.to_thread(self.cache.get, endpoint, params)
                if cached is not None:
                    cached["_from_cache"] = True
                    return cached

            estimated_cost_cents = self.config.default_cost_cents
            if self.budget is not None:
                exp_key = experiment_id or "global"
                if exp_key not in self._budget_locks:
                    async with self._budget_eviction_lock:
                        if exp_key not in self._budget_locks:
                            if len(self._budget_locks) >= self._max_budget_locks:
                                evicted = False
                                for old_key in list(self._budget_locks.keys()):
                                    if not self._budget_locks[old_key].locked():
                                        self._budget_locks.pop(old_key, None)
                                        evicted = True
                                        break
                                if not evicted:
                                    oldest_key = next(iter(self._budget_locks))
                                    await self._budget_locks[oldest_key].acquire()
                                    self._budget_locks.pop(oldest_key, None)
                            self._budget_locks[exp_key] = asyncio.Lock()
                        self._budget_locks.move_to_end(exp_key)
                else:
                    self._budget_locks.move_to_end(exp_key)
                async with self._budget_locks[exp_key]:
                    await asyncio.to_thread(self.budget.check, experiment_id, estimated_cost_cents)
                    raw = await self._post_with_retry(endpoint, [params])
                    await asyncio.to_thread(self.budget.record, experiment_id, estimated_cost_cents)
            else:
                raw = await self._post_with_retry(endpoint, [params])

            if self.cache is not None:
                await asyncio.to_thread(self.cache.set, endpoint, params, raw, experiment_id=experiment_id)
            return raw

    async def _post_with_retry(self, endpoint: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
        backoffs = [1.0, 2.0, 4.0]
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        last_error: Exception | None = None

        for attempt in range(len(backoffs) + 1):
            await self.rate_limiter.acquire()
            try:
                response = await self._client.post(url, json=payload)
                if 400 <= response.status_code < 500:
                    logger.error("DataforSEO permanent error", extra={"endpoint": endpoint, "payload": payload})
                    raise DataforSEOAPIError(f"DataforSEO request failed with {response.status_code}: {response.text}")
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError("Transient DataforSEO server error", request=response.request, response=response)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as exc:
                last_error = exc
                status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if status_code is not None and status_code < 500:
                    raise
                if attempt == len(backoffs):
                    break
                await self._sleep(backoffs[attempt])

        logger.error("DataforSEO retries exhausted", extra={"endpoint": endpoint, "payload": payload})
        raise DataforSEOAPIError(f"DataforSEO request failed after {len(backoffs)} retries") from last_error

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(auth=(self.config.login, self.config.password), timeout=30.0)
        return self._http_client

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    def _to_serp_response(self, raw: dict[str, Any], *, params: dict[str, Any], from_cache: bool) -> SERPResponse:
        ai_overview = self._find_ai_overview(raw)
        return SERPResponse(
            keyword=str(params["keyword"]),
            location_code=int(params["location_code"]),
            language_code=str(params["language_code"]),
            ai_overview=ai_overview,
            citations=self._extract_citations(ai_overview),
            raw=raw,
            timestamp=datetime.now(UTC),
            estimated_cost=Decimal(self.config.default_cost_cents) / Decimal(100),
            from_cache=from_cache,
        )

    def _find_ai_overview(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        tasks = raw.get("tasks", [])
        for task in tasks:
            for result in task.get("result", []) or []:
                for item in result.get("items", []) or []:
                    item_type = str(item.get("type", "")).lower()
                    if "ai_overview" in item_type or "ai overview" in item_type:
                        return item
        return None

    def _extract_citations(self, ai_overview: dict[str, Any] | None) -> list[str]:
        if ai_overview is None:
            return []
        citations: list[str] = []
        for key in ("references", "citations", "links"):
            for entry in ai_overview.get(key, []) or []:
                if isinstance(entry, str):
                    citations.append(entry)
                elif isinstance(entry, dict):
                    url = entry.get("url") or entry.get("link") or entry.get("domain")
                    if url:
                        citations.append(str(url))
        return citations
