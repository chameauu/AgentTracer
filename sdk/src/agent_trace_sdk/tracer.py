"""Main tracer for capturing AI agent traces."""
from __future__ import annotations

from typing import Any
from uuid import uuid4
from datetime import datetime, timezone

from .span import Span
from .exporter import HTTPExporter
from .domain.interfaces import ExportEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tracer:
    """Manages a trace run: creates spans and exports events."""

    _instance: Tracer | None = None

    def __init__(
        self,
        name: str,
        endpoint: str | None = None,
    ) -> None:
        self._name = name
        self._run_id = str(uuid4())
        self._root_span: Span | None = None
        self._exporter = HTTPExporter(endpoint=endpoint or "http://localhost:8000/api/v1/ingest/events")
        self._events: list[ExportEvent] = []

    @classmethod
    def get_instance(cls) -> Tracer | None:
        return cls._instance

    @classmethod
    def set_instance(cls, tracer: Tracer | None) -> None:
        cls._instance = tracer

    def start_span(
        self,
        name: str,
        span_type: str = "step",
        parent_id: str | None = None,
    ) -> Span:
        span = Span.create(
            run_id=self._run_id,
            name=name,
            span_type=span_type,
            parent_id=parent_id,
            tracer=self,
        )
        self._add_span_start_event(span)
        return span

    def _add_span_start_event(self, span: Span) -> None:
        event = ExportEvent(
            event_type="span_start",
            span_id=span.id,
            timestamp=span.started_at.isoformat(),
            data={
                "parent_id": span.parent_id,
                "name": span.name,
                "span_type": span.span_type,
                "attributes": span.attributes,
            },
        )
        self._events.append(event)

    def _end_span(self, span: Span) -> None:
        event = ExportEvent(
            event_type="span_end",
            span_id=span.id,
            timestamp=span.ended_at.isoformat() if span.ended_at else _utcnow().isoformat(),
            data={"attributes": span.attributes},
        )
        self._events.append(event)

    def _add_event(self, span_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event = ExportEvent(
            event_type="span_event",
            span_id=span_id,
            timestamp=_utcnow().isoformat(),
            data={"event_type": event_type, "payload": payload},
        )
        self._events.append(event)

    def flush(self) -> None:
        """Send all pending events to the backend."""
        if not self._events:
            return
        from .domain.interfaces import ExportBatch
        batch = ExportBatch(
            run_id=self._run_id,
            events=list(self._events),
            run_name=self._name,
        )
        import asyncio
        try:
            asyncio.run(self._exporter.export(batch))
            self._events.clear()
        except Exception as e:
            print(f"Failed to export events: {e}")

    def __enter__(self) -> Span:
        Tracer.set_instance(self)
        self._root_span = self.start_span(name=self._name, span_type="agent_run")
        return self._root_span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._root_span:
            self._root_span.ended_at = _utcnow()
            self._end_span(self._root_span)
        self.flush()
        Tracer.set_instance(None)