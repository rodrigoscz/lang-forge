from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.schema import Database, database_from_env


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = database_from_env()
    database.initialize()
    app.state.database = database
    yield


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


@app.get("/health")
def health() -> dict[str, str]:
    database: Database = app.state.database
    return {
        "status": "ok",
        "database": str(Path(database.path)),
    }
