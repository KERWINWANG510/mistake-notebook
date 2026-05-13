from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.migrate_sqlite import apply_sqlite_migrations
from app.routers import ai, analyze, auth, grades, mistakes, subjects
from app.seed import (
    backfill_mistake_user_ids,
    backfill_user_profiles,
    ensure_admin_user,
    ensure_missing_presets,
    run_seed,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if "sqlite" in settings.database_url:
        db_path = settings.database_url.split("///")[-1]
        Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(apply_sqlite_migrations)
    async with AsyncSessionLocal() as session:
        await run_seed(session)
        await ensure_missing_presets(session)
        await ensure_admin_user(session)
        await backfill_user_profiles(session)
        await backfill_mistake_user_ids(session)
    yield


settings = get_settings()
app = FastAPI(title="AI 错题本", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(subjects.router)
app.include_router(grades.router)
app.include_router(mistakes.router)
app.include_router(ai.router)
app.include_router(analyze.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
