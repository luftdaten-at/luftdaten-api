import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Umgebungsvariablen auslesen
DB_USER = os.getenv("POSTGRES_USER", "")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_NAME = os.getenv("POSTGRES_DB", "")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Async engine and session (FastAPI app)
async_engine = create_async_engine(ASYNC_DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine for Alembic / scripts that still use synchronous SQLAlchemy
sync_engine = create_engine(DATABASE_URL)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
