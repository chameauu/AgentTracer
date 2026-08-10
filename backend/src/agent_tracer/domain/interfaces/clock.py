"""Clock abstraction for testable time."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime


class IClock(ABC):
    @abstractmethod
    def utcnow(self) -> datetime: ...


class SystemClock(IClock):
    def utcnow(self) -> datetime:
        return datetime.now(UTC)


class MockClock(IClock):
    """Test double: returns a fixed time instead of the real wall clock."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)

    def utcnow(self) -> datetime:
        return self._now
