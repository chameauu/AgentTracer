"""Application service for ingesting span events."""

from __future__ import annotations

import uuid
from datetime import datetime

from ...domain.entities import AgentRun, SpanEvent, TraceNode
from ...domain.interfaces import (
    IClock,
    IRunRepository,
    ISpanEventRepository,
    ITraceNodeRepository,
    SystemClock,
)
from ...domain.value_objects import RunStatus, SpanType


class IngestService:
    """Orchestrates event ingestion using domain entities + repositories."""

    def __init__(
        self,
        run_repo: IRunRepository,
        node_repo: ITraceNodeRepository,
        event_repo: ISpanEventRepository,
        clock: IClock | None = None,
    ) -> None:
        self._runs = run_repo
        self._nodes = node_repo
        self._events = event_repo
        self._clock = clock or SystemClock()

    async def ingest(
        self,
        run_id: str,
        run_name: str | None,
        events: list[dict],
    ) -> int:
        """Process a batch of events; returns the number accepted."""
        run = await self._runs.get(run_id)
        if run is None:
            await self._runs.save(self._auto_create_run(run_id, run_name))
        accepted = 0
        for event in events:
            try:
                await self._process_event(run_id, event["type"], event["data"])
                accepted += 1
            except Exception as e:
                print(f"Failed to process event {event.get('type')}: {e}")
        return accepted

    def _auto_create_run(self, run_id: str, run_name: str | None) -> AgentRun:
        now = self._clock.utcnow()
        return AgentRun(
            id=run_id,
            name=run_name or f"run-{run_id[:8]}",
            status=RunStatus.RUNNING,
            started_at=now,
            created_at=now,
            updated_at=now,
        )

    def _parse_ts(self, ts: str | None) -> datetime:
        return datetime.fromisoformat(ts) if ts else self._clock.utcnow()

    async def _process_event(self, run_id: str, event_type: str, data: dict) -> None:
        if event_type == "span_start":
            await self._nodes.save(
                TraceNode(
                    id=data.get("span_id") or str(uuid.uuid4()),
                    run_id=run_id,
                    parent_id=data.get("parent_id"),
                    name=data.get("name") or "unknown",
                    span_type=SpanType(data.get("span_type") or "step"),
                    started_at=self._parse_ts(data.get("timestamp")),
                    attributes=data.get("attributes") or {},
                )
            )
        elif event_type == "span_end":
            span_id = data.get("span_id")
            if span_id:
                node = await self._nodes.get(span_id)
                if node is not None:
                    node.complete(self._parse_ts(data.get("timestamp")))
                    node.attributes = data.get("attributes") or {}
                    await self._nodes.save(node)
        elif event_type == "span_event":
            await self._events.save(
                SpanEvent(
                    id=str(uuid.uuid4()),
                    node_id=data.get("span_id") or "",
                    event_type=data.get("event_type") or "unknown",
                    timestamp=self._parse_ts(data.get("timestamp")),
                    payload=data.get("payload") or {},
                )
            )
