import json
import os
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

# Umgebungsvariablen auslesen
DB_USER = os.getenv("POSTGRES_USER", "")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_NAME = os.getenv("POSTGRES_DB", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# region agent log
def _agent_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict | None = None,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": "58b986",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "runId": run_id,
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, default=str) + "\n"
    for p in (
        Path(__file__).resolve().parent / "debug_58b986.ndjson",
        Path("/Users/silvioheinze/coding/luftdaten-api/.cursor/debug-58b986.log"),
    ):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            continue


def _async_pool_stats() -> dict:
    try:
        pool = async_engine.sync_engine.pool
        stats = {
            "checked_out": pool.checkedout(),
            "pool_size": pool.size(),
        }
        ofn = getattr(pool, "overflow", None)
        if callable(ofn):
            stats["overflow"] = ofn()
        return stats
    except Exception as exc:
        return {"error": str(exc)}


# endregion

# Async engine and session (FastAPI app)
# Larger pool: default 5 + overflow 10 exhausts under concurrent /statistics fallback + /station/current.
_pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "40"))
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_timeout=60,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# APScheduler runs asyncio.run() in worker threads; do not share the app pool across event loops.
scheduler_async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    poolclass=NullPool,
)
SchedulerAsyncSessionLocal = async_sessionmaker(
    scheduler_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine for Alembic / scripts that still use synchronous SQLAlchemy
sync_engine = create_engine(DATABASE_URL)

Base = declarative_base()


async def get_db():
    # region agent log
    _agent_log(
        "H1",
        "database.py:get_db:enter",
        "session_open",
        {"pool": _async_pool_stats()},
    )
    # endregion
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # region agent log
            _agent_log(
                "H2",
                "database.py:get_db:exit",
                "session_closing",
                {"pool": _async_pool_stats()},
            )
            # endregion
