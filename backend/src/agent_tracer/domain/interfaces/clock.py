"""Clock abstraction for testable time."""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
class IClock(ABC):
    @abstractmethod
    def utcnow(self) -> datetime: ...
class SystemClock(IClock):
    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)
class MockClock(IClock):
    """Test double: returns a fixed time instead of the real wall clock."""
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=timezone.utc)
    def utcnow(self) -> datetime:
        return self._now