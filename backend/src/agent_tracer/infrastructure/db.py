"""Async database engine + session factory (SQLAlchemy 2.0 + aiosqlite)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "agent_tracer.db"


def create_engine(db_path: Path = DEFAULT_DB_PATH) -> AsyncEngine:
    """Create the async SQLite engine for the given path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create all tables defined by the ORM models."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
