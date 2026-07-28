"""Data contracts and interfaces for the SDK."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExportEvent:
    """A single event to export to the backend."""

    event_type: str  # "span_start", "span_end", "span_event"
    span_id: str
    timestamp: str  # ISO format
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to backend-compatible format."""
        merged_data = {
            "span_id": self.span_id,
            "timestamp": self.timestamp,
            **self.data,
        }
        return {
            "type": self.event_type,
            "data": merged_data,
        }


@dataclass(frozen=True)
class ExportBatch:
    """Batch of events to export."""

    run_id: str
    events: list[ExportEvent]
    run_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to backend IngestRequest format."""
        result: dict[str, Any] = {
            "run_id": self.run_id,
            "events": [e.to_dict() for e in self.events],
        }
        if self.run_name is not None:
            result["run_name"] = self.run_name
        return result


class IEventExporter(ABC):
    """Abstract exporter for trace events."""

    @abstractmethod
    async def export(self, batch: ExportBatch) -> bool:
        ...

    @abstractmethod
    async def flush(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class ExportError(Exception):
    """Error during event export."""
    pass