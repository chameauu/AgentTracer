"""AgentTracer Backend - FastAPI entry point (clean architecture)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from agent_tracer.application import IngestService, RunNotFoundError, RunService
from agent_tracer.infrastructure import (
    SqlRunRepository,
    SqlSpanEventRepository,
    SqlTraceNodeRepository,
    create_engine,
    create_session_factory,
    init_db,
)


# ── Pydantic Schemas ────────────────────────────────────────────────────────
class IngestEvent(BaseModel):
    type: str  # "span_start" | "span_end" | "span_event"
    data: dict[str, Any]


class IngestRequest(BaseModel):
    run_id: str
    run_name: str | None = None
    events: list[IngestEvent]


class IngestResponse(BaseModel):
    accepted: int
    run_id: str


class RunResponse(BaseModel):
    id: str
    name: str
    status: str
    started_at: str
    ended_at: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = {}
    node_count: int | None = None


class TraceNodeResponse(BaseModel):
    id: str
    name: str
    span_type: str
    started_at: str
    ended_at: str | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = {}
    children: list[TraceNodeResponse] = []
    events: list[dict[str, Any]] = []


class TraceTreeResponse(BaseModel):
    run_id: str
    root: TraceNodeResponse | None = None


# ── App factory / DI container ─────────────────────────────────────────────
def create_app(engine: AsyncEngine | None = None) -> FastAPI:
    """Build the FastAPI app with injected infrastructure dependencies."""
    if engine is None:
        engine = create_engine()
    session_factory = create_session_factory(engine)
    run_repo = SqlRunRepository(session_factory)
    node_repo = SqlTraceNodeRepository(session_factory)
    event_repo = SqlSpanEventRepository(session_factory)
    ingest_service = IngestService(run_repo, node_repo, event_repo)
    run_service = RunService(run_repo, node_repo, event_repo)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="AgentTracer", version="0.1.0", lifespan=lifespan)

    @app.post("/api/v1/ingest/events", response_model=IngestResponse, status_code=202)
    async def ingest_events(request: IngestRequest) -> IngestResponse:
        accepted = await ingest_service.ingest(
            request.run_id,
            request.run_name,
            [e.model_dump() for e in request.events],
        )
        return IngestResponse(accepted=accepted, run_id=request.run_id)

    @app.get("/api/v1/runs")
    async def list_runs(limit: int = 20, offset: int = 0, status: str | None = None) -> dict:
        return await run_service.list_runs(limit=limit, offset=offset, status=status)

    @app.get("/api/v1/runs/{run_id}", response_model=RunResponse)
    async def get_run(run_id: str) -> RunResponse:
        try:
            return await run_service.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found") from exc

    @app.get("/api/v1/runs/{run_id}/tree", response_model=TraceTreeResponse)
    async def get_run_tree(run_id: str) -> TraceTreeResponse:
        try:
            return await run_service.get_run_tree(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found") from exc

    @app.get("/api/v1/health")
    async def health_check() -> dict:
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/health")
    async def health_check_root() -> dict:
        return {"status": "healthy", "version": "0.1.0"}

    return app


app = create_app()
