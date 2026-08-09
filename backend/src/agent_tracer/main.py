"""Minimal AgentTracer Backend"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ── Database ──────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "agent_tracer.db"


def get_db() -> sqlite3.Connection:
    """Get a database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            started_at TEXT NOT NULL,
            ended_at TEXT,
            metadata_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trace_nodes (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
            parent_id TEXT REFERENCES trace_nodes(id),
            name TEXT NOT NULL,
            span_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            attributes_json TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS span_events (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL REFERENCES trace_nodes(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload_json TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_nodes_run_id ON trace_nodes(run_id);
        CREATE INDEX IF NOT EXISTS idx_events_node_id ON span_events(node_id);
    """)
    conn.commit()
    conn.close()


# ── Pydantic Schemas ──────────────────────────────────────────────────────


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


# ── Helpers ────────────────────────────────────────────────────────────────


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(ts: str | None) -> str:
    return ts or _utcnow()


def _calc_duration_ms(start: str, end: str | None) -> float | None:
    if not end:
        return None
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        return (e - s).total_seconds() * 1000
    except (ValueError, TypeError):
        return None


# ── App ────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AgentTracer", version="0.1.0", lifespan=lifespan)


# ── Ingestion ──────────────────────────────────────────────────────────────


@app.post("/api/v1/ingest/events", response_model=IngestResponse, status_code=202)
async def ingest_events(request: IngestRequest) -> IngestResponse:
    conn = get_db()
    accepted = 0

    try:
        # Ensure run exists
        run = conn.execute(
            "SELECT id FROM runs WHERE id = ?", (request.run_id,)
        ).fetchone()
        if not run:
            now = _utcnow()
            conn.execute(
                "INSERT INTO runs (id, name, status, started_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request.run_id,
                    request.run_name or f"run-{request.run_id[:8]}",
                    "running",
                    now,
                    now,
                    now,
                ),
            )

        for event in request.events:
            try:
                data = event.data
                if event.type == "span_start":
                    span_id = data.get("span_id", str(uuid.uuid4()))
                    conn.execute(
                        "INSERT OR REPLACE INTO trace_nodes (id, run_id, parent_id, name, span_type, started_at, attributes_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            span_id,
                            request.run_id,
                            data.get("parent_id"),
                            data.get("name", "unknown"),
                            data.get("span_type", "step"),
                            _parse_timestamp(data.get("timestamp")),
                            json.dumps(data.get("attributes", {})),
                        ),
                    )
                elif event.type == "span_end":
                    span_id = data.get("span_id")
                    if span_id:
                        conn.execute(
                            "UPDATE trace_nodes SET ended_at = ?, attributes_json = ? WHERE id = ?",
                            (
                                _parse_timestamp(data.get("timestamp")),
                                json.dumps(data.get("attributes", {})),
                                span_id,
                            ),
                        )
                elif event.type == "span_event":
                    conn.execute(
                        "INSERT INTO span_events (id, node_id, event_type, timestamp, payload_json) VALUES (?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            data.get("span_id", ""),
                            data.get("event_type", "unknown"),
                            _parse_timestamp(data.get("timestamp")),
                            json.dumps(data.get("payload", {})),
                        ),
                    )
                accepted += 1
            except Exception as e:
                print(f"Failed to process event {event.type}: {e}")

        conn.commit()
    finally:
        conn.close()

    return IngestResponse(accepted=accepted, run_id=request.run_id)


# ── Run listing ────────────────────────────────────────────────────────────


@app.get("/api/v1/runs")
async def list_runs(limit: int = 20, offset: int = 0, status: str | None = None):
    conn = get_db()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM runs WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE status = ?", (status,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

        runs = []
        for row in rows:
            node_count = conn.execute(
                "SELECT COUNT(*) FROM trace_nodes WHERE run_id = ?", (row["id"],)
            ).fetchone()[0]
            runs.append(
                RunResponse(
                    id=row["id"],
                    name=row["name"],
                    status=row["status"],
                    started_at=row["started_at"],
                    ended_at=row["ended_at"],
                    duration_ms=_calc_duration_ms(row["started_at"], row["ended_at"]),
                    metadata=json.loads(row["metadata_json"] or "{}"),
                    node_count=node_count,
                )
            )

        return {
            "runs": [r.model_dump() for r in runs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        node_count = conn.execute(
            "SELECT COUNT(*) FROM trace_nodes WHERE run_id = ?", (run_id,)
        ).fetchone()[0]

        return RunResponse(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_ms=_calc_duration_ms(row["started_at"], row["ended_at"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            node_count=node_count,
        ).model_dump()
    finally:
        conn.close()


# ── Trace Tree ─────────────────────────────────────────────────────────────


def _build_tree(nodes: list[dict], events_map: dict[str, list]) -> list[dict]:
    """Build tree from flat node list."""
    node_map = {n["id"]: n for n in nodes}
    for n in nodes:
        n["children"] = []
        n["events"] = events_map.get(n["id"], [])

    roots = []
    for n in nodes:
        if n.get("parent_id") is None:
            roots.append(n)
        elif n["parent_id"] in node_map:
            node_map[n["parent_id"]]["children"].append(n)
    return roots


@app.get("/api/v1/runs/{run_id}/tree")
async def get_run_tree(run_id: str):
    conn = get_db()
    try:
        # Verify run exists
        run = conn.execute("SELECT id FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Get all nodes
        node_rows = conn.execute(
            "SELECT * FROM trace_nodes WHERE run_id = ? ORDER BY started_at", (run_id,)
        ).fetchall()
        if not node_rows:
            return TraceTreeResponse(run_id=run_id, root=None).model_dump()

        # Get all events for this run's nodes
        node_ids = [r["id"] for r in node_rows]
        events_map: dict[str, list] = {}
        if node_ids:
            placeholders = ",".join("?" * len(node_ids))
            event_rows = conn.execute(
                f"SELECT * FROM span_events WHERE node_id IN ({placeholders}) ORDER BY timestamp",
                node_ids,
            ).fetchall()
            for er in event_rows:
                nid = er["node_id"]
                if nid not in events_map:
                    events_map[nid] = []
                events_map[nid].append(
                    {
                        "id": er["id"],
                        "event_type": er["event_type"],
                        "timestamp": er["timestamp"],
                        "payload": json.loads(er["payload_json"] or "{}"),
                    }
                )

        # Convert to dicts
        nodes = []
        for r in node_rows:
            nodes.append(
                {
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "parent_id": r["parent_id"],
                    "name": r["name"],
                    "span_type": r["span_type"],
                    "started_at": r["started_at"],
                    "ended_at": r["ended_at"],
                    "duration_ms": _calc_duration_ms(r["started_at"], r["ended_at"]),
                    "attributes": json.loads(r["attributes_json"] or "{}"),
                }
            )

        roots = _build_tree(nodes, events_map)

        def _to_response(n: dict) -> dict:
            return {
                "id": n["id"],
                "name": n["name"],
                "span_type": n["span_type"],
                "started_at": n["started_at"],
                "ended_at": n["ended_at"],
                "duration_ms": n["duration_ms"],
                "attributes": n["attributes"],
                "children": [_to_response(c) for c in n["children"]],
                "events": n["events"],
            }

        root = _to_response(roots[0]) if roots else None
        return TraceTreeResponse(run_id=run_id, root=root).model_dump()
    finally:
        conn.close()


# ── Health ─────────────────────────────────────────────────────────────────


@app.get("/api/v1/health")
async def health_check() -> dict:
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/health")
async def health_check_root() -> dict:
    return {"status": "healthy", "version": "0.1.0"}
