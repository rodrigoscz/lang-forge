from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.dataforseo.budget import BudgetExceededError, QueryBudget
from app.dataforseo.cache import ApiCache
from app.dataforseo.client import DataforSEOAPIError, DataforSEOClient, DataforSEOConfig
from app.dataforseo.rate_limit import AsyncRateLimiter
from app.db.schema import Database


def temp_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "experiments.db")
    database.initialize()
    return database


class FakeHTTPClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, json: list[dict[str, Any]]) -> httpx.Response:
        self.calls.append({"url": url, "json": json})
        response = self.responses.pop(0)
        response.request = httpx.Request("POST", url)
        return response

    async def aclose(self) -> None:
        return None


def config() -> DataforSEOConfig:
    return DataforSEOConfig(login="login", password="password", rate_limit_rps=100, default_cost_cents=2)


def dataforseo_payload() -> dict[str, Any]:
    return {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {
                                "type": "ai_overview",
                                "text": "Overview",
                                "references": [{"url": "https://example.com/page"}],
                            }
                        ]
                    }
                ]
            }
        ]
    }


def test_client_retries_transient_errors_then_returns_structured_response(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        fake_http = FakeHTTPClient(
            [
                httpx.Response(503, json={"status": "try later"}),
                httpx.Response(503, json={"status": "try later"}),
                httpx.Response(200, json=dataforseo_payload()),
            ]
        )
        sleeps: list[float] = []
        client = DataforSEOClient(
            config(),
            cache=ApiCache(database),
            budget=QueryBudget(database),
            http_client=fake_http,  # type: ignore[arg-type]
        )

        async def record_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        client._sleep = record_sleep  # type: ignore[method-assign]

        response = await client.query_serp(keyword="best running shoes", experiment_id="001-content-structure")

        assert len(fake_http.calls) == 3
        assert sleeps == [1.0, 2.0]
        assert response.ai_overview is not None
        assert response.citations == ["https://example.com/page"]

    asyncio.run(run())


def test_client_does_not_retry_permanent_errors() -> None:
    async def run() -> None:
        fake_http = FakeHTTPClient([httpx.Response(400, text="bad request")])
        client = DataforSEOClient(config(), http_client=fake_http)  # type: ignore[arg-type]

        with pytest.raises(DataforSEOAPIError):
            await client.query_serp(keyword="bad", experiment_id="001-content-structure")

        assert len(fake_http.calls) == 1

    asyncio.run(run())


def test_client_raises_after_three_transient_retries() -> None:
    async def run() -> None:
        fake_http = FakeHTTPClient(
            [
                httpx.Response(503, json={"status": "try later"}),
                httpx.Response(503, json={"status": "try later"}),
                httpx.Response(503, json={"status": "try later"}),
                httpx.Response(503, json={"status": "try later"}),
            ]
        )
        sleeps: list[float] = []
        client = DataforSEOClient(config(), http_client=fake_http)  # type: ignore[arg-type]

        async def record_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        client._sleep = record_sleep  # type: ignore[method-assign]

        with pytest.raises(DataforSEOAPIError, match="3 retries"):
            await client.query_serp(keyword="transient", experiment_id="001-content-structure")

        assert len(fake_http.calls) == 4
        assert sleeps == [1.0, 2.0, 4.0]

    asyncio.run(run())


def test_budget_rejects_query_that_would_exceed_monthly_ceiling(tmp_path: Path) -> None:
    database = temp_database(tmp_path)
    budget = QueryBudget(database, monthly_budget_cents=3, per_experiment_limit=500)

    budget.record("001-content-structure", 2)

    with pytest.raises(BudgetExceededError, match="Monthly budget exceeded"):
        budget.check("001-content-structure", 2)


def test_budget_rejects_query_after_experiment_limit(tmp_path: Path) -> None:
    database = temp_database(tmp_path)
    budget = QueryBudget(database, monthly_budget_cents=100, per_experiment_limit=1)

    budget.record("001-content-structure", 2)

    with pytest.raises(BudgetExceededError, match="query limit"):
        budget.check("001-content-structure", 2)


def test_cache_hit_bypasses_budget_and_api_call(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        cache = ApiCache(database)
        budget = QueryBudget(database, monthly_budget_cents=2)
        params = {"keyword": "best running shoes", "location_code": 2840, "language_code": "en", "device": "desktop"}
        cache.set("/serp/google/organic/live/advanced", params, dataforseo_payload(), experiment_id="001-content-structure")
        fake_http = FakeHTTPClient([httpx.Response(200, json=dataforseo_payload())])
        client = DataforSEOClient(config(), cache=cache, budget=budget, http_client=fake_http)  # type: ignore[arg-type]

        first = await client.query_serp(keyword="best running shoes", experiment_id="001-content-structure")
        second = await client.query_serp(keyword="best running shoes", experiment_id="001-content-structure")

        assert first.from_cache is True
        assert second.from_cache is True
        assert fake_http.calls == []
        assert budget.status("001-content-structure").query_count == 0

    asyncio.run(run())


def test_control_query_bypasses_cache_and_records_budget(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        cache = ApiCache(database)
        params = {"keyword": "control", "location_code": 2840, "language_code": "en", "device": "desktop"}
        cache.set("/serp/google/organic/live/advanced", params, dataforseo_payload(), experiment_id="001-content-structure")
        fake_http = FakeHTTPClient([httpx.Response(200, json=dataforseo_payload())])
        budget = QueryBudget(database)
        client = DataforSEOClient(config(), cache=cache, budget=budget, http_client=fake_http)  # type: ignore[arg-type]

        response = await client.query_serp(
            keyword="control",
            experiment_id="001-content-structure",
            control_query=True,
        )

        assert response.from_cache is False
        assert len(fake_http.calls) == 1
        assert budget.status("001-content-structure").query_count == 1

    asyncio.run(run())


def test_rate_limiter_queues_requests_over_configured_rps() -> None:
    async def run() -> None:
        current_time = 0.0
        sleeps: list[float] = []

        def clock() -> float:
            return current_time

        async def sleep(seconds: float) -> None:
            nonlocal current_time
            sleeps.append(seconds)
            current_time += seconds

        limiter = AsyncRateLimiter(2, clock=clock, sleep=sleep)

        await asyncio.gather(limiter.acquire(), limiter.acquire(), limiter.acquire())

        assert sleeps == [1.0]

    asyncio.run(run())


def test_lock_eviction_when_max_locks_exceeded() -> None:
    async def run() -> None:
        client = DataforSEOClient(config(), http_client=FakeHTTPClient([]))  # type: ignore[arg-type]
        client._max_locks = 3

        for i in range(3):
            client._locks[f"key-{i}"] = asyncio.Lock()

        assert len(client._locks) == 3

        client._locks["key-4"] = asyncio.Lock()
        assert len(client._locks) == 4

    asyncio.run(run())



def test_budget_lock_eviction_when_max_exceeded() -> None:
    async def run() -> None:
        client = DataforSEOClient(config(), http_client=FakeHTTPClient([]))  # type: ignore[arg-type]
        client._max_budget_locks = 3

        for i in range(3):
            client._budget_locks[f"exp-{i}"] = asyncio.Lock()

        assert len(client._budget_locks) == 3

        client._budget_locks["exp-4"] = asyncio.Lock()
        assert len(client._budget_locks) == 4

    asyncio.run(run())


def test_budget_exceeded_mid_batch_continues(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        budget = QueryBudget(database, monthly_budget_cents=4, per_experiment_limit=2)
        fake_http = FakeHTTPClient([
            httpx.Response(200, json=dataforseo_payload()),
            httpx.Response(200, json=dataforseo_payload()),
            httpx.Response(200, json=dataforseo_payload()),
        ])
        client = DataforSEOClient(
            config(),
            cache=ApiCache(database),
            budget=budget,
            http_client=fake_http,  # type: ignore[arg-type]
        )

        results = []
        for i in range(3):
            try:
                response = await client.query_serp(keyword=f"query-{i}", experiment_id="001-test")
                results.append({"query": f"query-{i}", "success": True})
            except (DataforSEOAPIError, BudgetExceededError) as e:
                results.append({"query": f"query-{i}", "success": False, "error": str(e)})

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is True
        assert results[2]["success"] is False
        assert "limit" in results[2]["error"].lower()

    asyncio.run(run())


def test_budget_lock_held_during_api_call(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        budget = QueryBudget(database, monthly_budget_cents=100, per_experiment_limit=50)
        fake_http = FakeHTTPClient([
            httpx.Response(200, json=dataforseo_payload()),
            httpx.Response(200, json=dataforseo_payload()),
        ])
        client = DataforSEOClient(
            config(),
            cache=ApiCache(database),
            budget=budget,
            http_client=fake_http,  # type: ignore[arg-type]
        )

        async def query1() -> None:
            await client.query_serp(keyword="query-1", experiment_id="001-test")

        async def query2() -> None:
            await asyncio.sleep(0.001)
            await client.query_serp(keyword="query-2", experiment_id="001-test")

        await asyncio.gather(query1(), query2())

        status = budget.status("001-test")
        assert status.query_count == 2

    asyncio.run(run())


def test_lock_eviction_via_execute_query(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        responses = [httpx.Response(200, json=dataforseo_payload()) for _ in range(10)]
        fake_http = FakeHTTPClient(responses)
        client = DataforSEOClient(
            config(),
            cache=ApiCache(database),
            budget=QueryBudget(database),
            http_client=fake_http,  # type: ignore[arg-type],
        )
        client._max_locks = 5

        tasks = [
            client._execute_query(
                endpoint="/serp/google/organic/live/advanced",
                params={"keyword": f"query-{i}", "location_code": 2840, "language_code": "en", "device": "desktop"},
                experiment_id="test-exp",
                force_fresh=True,
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        assert all(not isinstance(r, Exception) for r in results), f"Unexpected exceptions: {[r for r in results if isinstance(r, Exception)]}"
        assert len(client._locks) <= client._max_locks

    asyncio.run(run())


def test_budget_enforcement_under_concurrent_load(tmp_path: Path) -> None:
    async def run() -> None:
        database = temp_database(tmp_path)
        budget = QueryBudget(database, monthly_budget_cents=10, per_experiment_limit=3)
        responses = [httpx.Response(200, json=dataforseo_payload()) for _ in range(10)]
        fake_http = FakeHTTPClient(responses)
        client = DataforSEOClient(
            config(),
            cache=ApiCache(database),
            budget=budget,
            http_client=fake_http,  # type: ignore[arg-type],
        )

        tasks = [
            client._execute_query(
                endpoint="/serp/google/organic/live/advanced",
                params={"keyword": f"query-{i}", "location_code": 2840, "language_code": "en", "device": "desktop"},
                experiment_id="test-exp",
                force_fresh=True,
            )
            for i in range(6)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, (BudgetExceededError, DataforSEOAPIError))]
        assert len(successes) == 3
        assert len(failures) == 3
        assert budget.status("test-exp").query_count == 3

    asyncio.run(run())
