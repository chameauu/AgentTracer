from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from .. import RunStatus


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AgentRun:
    id: str
    name: str
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be before started_at")

    @property
    def duration_ms(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds() * 1000

    @classmethod
    def create(cls, name: str, **kwargs) -> AgentRun:
        now = _utcnow()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            status=RunStatus.RUNNING,
            started_at=now,
            created_at=now,
            updated_at=now,
            **kwargs,
        )

    def complete(self, ended_at: datetime | None = None) -> AgentRun:
        """Transition to COMPLETED. Returns a NEW instance (frozen)."""
        return replace(
            self,
            status=RunStatus.COMPLETED,
            ended_at=ended_at or _utcnow(),
            updated_at=_utcnow(),
        )

    def fail(self, ended_at: datetime | None = None) -> AgentRun:
        """Transition to FAILED. Returns a NEW instance (frozen)."""
        return replace(
            self,
            status=RunStatus.FAILED,
            ended_at=ended_at or _utcnow(),
            updated_at=_utcnow(),
        )
