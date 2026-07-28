"""Span dataclass for tracing units of work."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .tracer import Tracer


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Span:
    """A single unit of work within a trace."""

    id: str
    run_id: str
    name: str
    span_type: str
    started_at: datetime
    tracer: Tracer | None = None
    parent_id: str | None = None
    ended_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        run_id: str,
        name: str,
        span_type: str = "step",
        parent_id: str | None = None,
        tracer: Tracer | None = None,
    ) -> Span:
        return cls(
            id=str(uuid4()),
            run_id=run_id,
            name=name,
            span_type=span_type,
            started_at=_utcnow(),
            parent_id=parent_id,
            tracer=tracer,
        )

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if self.tracer:
            self.tracer._add_event(
                span_id=self.id,
                event_type=event_type,
                payload=payload or {},
            )

    def complete(self) -> None:
        self.ended_at = _utcnow()
        if self.tracer:
            self.tracer._end_span(self)