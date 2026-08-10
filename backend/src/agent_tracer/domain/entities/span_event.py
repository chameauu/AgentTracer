"""SpanEvent — a terminal point-in-time annotation on a node (frozen)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SpanEvent:
    id: str
    node_id: str
    event_type: str
    timestamp: datetime
    payload: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id cannot be empty")
        if not self.node_id:
            raise ValueError("node_id cannot be empty")
        if not self.event_type:
            raise ValueError("event_type cannot be empty")

    @classmethod
    def create(
        cls,
        node_id: str,
        event_type: str,
        payload: dict | None = None,
        **kwargs,
    ) -> SpanEvent:
        return cls(
            id=str(uuid.uuid4()),
            node_id=node_id,
            event_type=event_type,
            timestamp=_utcnow(),
            payload=payload or {},
            **kwargs,
        )
