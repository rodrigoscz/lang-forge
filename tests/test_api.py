from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Tuple

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from app.dataforseo.cache import ApiCache
from app.dataforseo.client import DataforSEOClient, DataforSEOConfig
from app.db.schema import Database


def _fake_client(tmp_path: Path) -> Tuple[FastAPI, Database]:
    from main import app

    database = Database(tmp_path / "test_experiments.db")
    database.initialize()
    config = DataforSEOConfig(login="test", password="test", rate_limit_rps=100)
    cache = ApiCache(database)
    client = DataforSEOClient(config, cache=cache, http_client=_FakeHTTPClient([]))
    app.state.database = database
    app.state.dataforseo_client = client
    return app, database


class _FakeHTTPClient:
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


def _dataforseo_payload() -> dict[str, Any]:
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


def test_health_ok(tmp_path: Path) -> None:
    async def run() -> None:
        app, _ = _fake_client(tmp_path)
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "experiments.db" in data["database"]

    asyncio.run(run())


def test_query_serp_success(tmp_path: Path) -> None:
    async def run() -> None:
        app, database = _fake_client(tmp_path)
        fake_http = _FakeHTTPClient([httpx.Response(200, json=_dataforseo_payload())])
        app.state.dataforseo_client = DataforSEOClient(
            DataforSEOConfig(login="test", password="test", rate_limit_rps=100),
            cache=ApiCache(database),
            http_client=fake_http,
        )
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post(
                "/api/serp/query",
                json={"experiment_id": "001-test", "keyword": "test query"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["keyword"] == "test query"
        assert data["citations"] == ["https://example.com/page"]

    asyncio.run(run())


def test_query_ai_overview(tmp_path: Path) -> None:
    async def run() -> None:
        app, database = _fake_client(tmp_path)
        fake_http = _FakeHTTPClient([httpx.Response(200, json=_dataforseo_payload())])
        app.state.dataforseo_client = DataforSEOClient(
            DataforSEOConfig(login="test", password="test", rate_limit_rps=100),
            cache=ApiCache(database),
            http_client=fake_http,
        )
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post(
                "/api/serp/query",
                json={"experiment_id": "001-test", "keyword": "test ai", "endpoint": "ai_overview"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["keyword"] == "test ai"

    asyncio.run(run())


def test_query_budget_exceeded_returns_402(tmp_path: Path) -> None:
    async def run() -> None:
        app, database = _fake_client(tmp_path)
        from app.dataforseo.budget import QueryBudget

        budget = QueryBudget(database, monthly_budget_cents=1, per_experiment_limit=1)
        budget.record("001-test", 1)

        app.state.dataforseo_client = DataforSEOClient(
            DataforSEOConfig(login="test", password="test", rate_limit_rps=100),
            cache=ApiCache(database),
            budget=budget,
            http_client=_FakeHTTPClient([]),
        )
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post(
                "/api/serp/query",
                json={"experiment_id": "001-test", "keyword": "budget test"},
            )
        assert response.status_code == 402
        assert "limit" in response.json()["detail"].lower()

    asyncio.run(run())


def test_query_api_error_returns_502(tmp_path: Path) -> None:
    async def run() -> None:
        app, database = _fake_client(tmp_path)
        fake_http = _FakeHTTPClient([httpx.Response(400, text="bad request")])
        app.state.dataforseo_client = DataforSEOClient(
            DataforSEOConfig(login="test", password="test", rate_limit_rps=100),
            cache=ApiCache(database),
            http_client=fake_http,
        )
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post(
                "/api/serp/query",
                json={"experiment_id": "001-test", "keyword": "api error"},
            )
        assert response.status_code == 502

    asyncio.run(run())


def test_budget_status(tmp_path: Path) -> None:
    async def run() -> None:
        app, database = _fake_client(tmp_path)
        from app.dataforseo.budget import QueryBudget

        budget = QueryBudget(database, monthly_budget_cents=100, per_experiment_limit=10)
        budget.record("001-test", 2)
        app.state.dataforseo_client = DataforSEOClient(
            DataforSEOConfig(login="test", password="test", rate_limit_rps=100),
            budget=budget,
            http_client=_FakeHTTPClient([]),
        )
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.get("/api/budget/status", params={"experiment_id": "001-test"})
        assert response.status_code == 200
        data = response.json()
        assert data["experiment_id"] == "001-test"
        assert data["spent_cents"] == 2
        assert data["query_count"] == 1

    asyncio.run(run())


def test_cache_invalidate(tmp_path: Path) -> None:
    async def run() -> None:
        app, database = _fake_client(tmp_path)
        cache = ApiCache(database)
        cache.set("/test/ep", {"key": "val"}, {"result": "ok"}, experiment_id="001-test")
        app.state.dataforseo_client = DataforSEOClient(
            DataforSEOConfig(login="test", password="test", rate_limit_rps=100),
            cache=cache,
            http_client=_FakeHTTPClient([]),
        )
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post("/api/cache/invalidate", json={"experiment_id": "001-test"})
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] >= 1

    asyncio.run(run())
