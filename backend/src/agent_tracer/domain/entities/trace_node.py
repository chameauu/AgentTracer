from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ..value_objects import SpanType

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
@dataclass
class TraceNode:
    id: str
    run_id: str
    name: str
    span_type: SpanType
    started_at: datetime
    parent_id: str | None = None
    ended_at: datetime | None = None
    attributes: dict = field(default_factory=dict)
    children: list[TraceNode] = field(default_factory=list)
    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id cannot be empty")
        if not self.run_id:
            raise ValueError("run_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
    @property
    def duration_ms(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds() * 1000
    @classmethod
    def create(
        cls,
        run_id: str,
        name: str,
        span_type: SpanType,
        parent_id: str | None = None,
        **kwargs,
    ) -> TraceNode:
        return cls(
            id=str(uuid.uuid4()),
            run_id=run_id,
            name=name,
            span_type=span_type,
            started_at=_utcnow(),
            parent_id=parent_id,
            **kwargs,
        )
    def add_child(self, node: TraceNode) -> None:
        self.children.append(node)
    def is_root(self) -> bool:
        return self.parent_id is None
    def complete(self, ended_at: datetime | None = None) -> None:
        self.ended_at = ended_at or _utcnow()