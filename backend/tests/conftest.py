"""Shared test fixtures for AgentTracer backend tests.
Each test gets a fresh in-memory SQLite engine (single shared connection),
so no test database files are created and no DB_PATH monkeypatching is needed.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

from agent_tracer.application import IngestService, RunService
from agent_tracer.infrastructure import (
    SqlRunRepository,
    SqlSpanEventRepository,
    SqlTraceNodeRepository,
    create_session_factory,
    init_db,
)
from agent_tracer.main import create_app


class Services(NamedTuple):
    """Application services wired to the shared in-memory engine."""

    ingest: IngestService
    run: RunService


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncEngine:
    """Fresh in-memory SQLite engine per test (one shared connection)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def services(engine: AsyncEngine) -> Services:
    """Build repositories + application services on the in-memory engine."""
    session_factory = create_session_factory(engine)
    run_repo = SqlRunRepository(session_factory)
    node_repo = SqlTraceNodeRepository(session_factory)
    event_repo = SqlSpanEventRepository(session_factory)
    return Services(
        ingest=IngestService(run_repo, node_repo, event_repo),
        run=RunService(run_repo, node_repo, event_repo),
    )


@pytest_asyncio.fixture(scope="function")
async def client(engine: AsyncEngine) -> AsyncClient:
    """HTTP client against the FastAPI app on the in-memory engine."""
    app = create_app(engine=engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
