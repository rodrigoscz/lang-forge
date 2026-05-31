from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.dataforseo import ApiCache, DataforSEOClient, DataforSEOConfig, QueryBudget
from app.dataforseo.budget import BudgetExceededError
from app.dataforseo.client import DataforSEOAPIError, DataforSEOConfigError
from app.db.schema import Database, database_from_env


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = database_from_env()
    database.initialize()
    app.state.database = database
    client = _dataforseo_client(database)
    app.state.dataforseo_client = client
    yield
    await client.close()


app = FastAPI(
    title="Lang Forge API",
    description="AI SEO Lab backend for experiments, data collection, and analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SERPQueryRequest(BaseModel):
    experiment_id: str = Field(min_length=1, pattern=r"^\d{3}-[a-z0-9-]+$")
    keyword: str = Field(min_length=1)
    location_code: int | None = None
    language_code: str | None = None
    device: Literal["desktop", "mobile"] = "desktop"
    force_fresh: bool = False
    control_query: bool = False
    endpoint: Literal["serp", "ai_overview"] = "serp"


class CacheInvalidateRequest(BaseModel):
    experiment_id: str | None = None
    endpoint: str | None = None
    params: dict[str, Any] | None = None


class BudgetStatusResponse(BaseModel):
    experiment_id: str
    period_start: str
    period_end: str
    monthly_budget_cents: int
    spent_cents: int
    query_count: int
    remaining_cents: int


@app.get("/health")
def health() -> dict[str, str]:
    database: Database = app.state.database
    return {
        "status": "ok",
        "database": str(Path(database.path)),
    }


@app.post("/api/serp/query")
async def query_serp(request: SERPQueryRequest) -> dict[str, Any]:
    try:
        client: DataforSEOClient = app.state.dataforseo_client
        if request.endpoint == "ai_overview":
            response = await client.query_ai_overview(
                keyword=request.keyword,
                experiment_id=request.experiment_id,
                location_code=request.location_code,
                language_code=request.language_code,
                force_fresh=request.force_fresh,
                control_query=request.control_query,
            )
        else:
            response = await client.query_serp(
                keyword=request.keyword,
                experiment_id=request.experiment_id,
                location_code=request.location_code,
                language_code=request.language_code,
                device="mobile" if request.device == "mobile" else "desktop",
                force_fresh=request.force_fresh,
                control_query=request.control_query,
            )
        return response.model_dump(mode="json")
    except DataforSEOConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BudgetExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except DataforSEOAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/budget/status")
def budget_status(experiment_id: str) -> BudgetStatusResponse:
    status = _query_budget().status(experiment_id)
    return BudgetStatusResponse(**status.__dict__)


@app.post("/api/cache/invalidate")
def invalidate_cache(request: CacheInvalidateRequest) -> dict[str, int]:
    deleted = ApiCache(_database()).invalidate(
        endpoint=request.endpoint,
        params=request.params,
        experiment_id=request.experiment_id,
    )
    return {"deleted": deleted}


def _database() -> Database:
    return app.state.database


def _query_budget() -> QueryBudget:
    return QueryBudget(
        _database(),
        monthly_budget_cents=int(os.getenv("MONTHLY_BUDGET_CENTS", "10000")),
        per_experiment_limit=int(os.getenv("EXPERIMENT_QUERY_LIMIT", "500")),
    )


def _dataforseo_client(database: Database | None = None) -> DataforSEOClient:
    db = database or _database()
    config = DataforSEOConfig.from_env()
    return DataforSEOClient(
        config,
        cache=ApiCache(db),
        budget=QueryBudget(
            db,
            monthly_budget_cents=config.monthly_budget_cents,
            per_experiment_limit=config.per_experiment_limit,
        ),
    )


# Serve Astro frontend (must be after API routes)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount(
        "/_astro",
        StaticFiles(directory=_frontend_dist / "_astro"),
        name="astro-assets",
    )
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Try to serve exact file first
        file_path = _frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Fallback to index.html for SPA routing
        index_path = _frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not built")
