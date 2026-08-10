from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities import AgentRun, SpanEvent, TraceNode
from ..value_objects import RunStatus


class IRunRepository(ABC):
    """Persistence contract for agent runs."""

    @abstractmethod
    def save(self, run: AgentRun) -> None:
        """Insert or update a run (upsert by id)."""

    @abstractmethod
    def get(self, run_id: str) -> AgentRun | None:
        """Fetch a run by id, or None if it does not exist."""

    @abstractmethod
    def list(
        self, limit: int = 20, offset: int = 0, status: RunStatus | None = None
    ) -> list[AgentRun]:
        """List runs newest-first, optionally filtered by status."""

    @abstractmethod
    def count(self, status: RunStatus | None = None) -> int:
        """Count runs, optionally filtered by status."""


class ITraceNodeRepository(ABC):
    """Persistence contract for trace tree nodes."""

    @abstractmethod
    def save(self, node: TraceNode) -> None:
        """Insert or update a node (upsert by id)."""

    @abstractmethod
    def get(self, node_id: str) -> TraceNode | None:
        """Fetch a node by id, or None if it does not exist."""

    @abstractmethod
    def list_by_run(self, run_id: str) -> list[TraceNode]:
        """List all nodes belonging to a run."""


class ISpanEventRepository(ABC):
    """Persistence contract for span events."""

    @abstractmethod
    def save(self, event: SpanEvent) -> None:
        """Insert or update a span event (upsert by id)."""

    @abstractmethod
    def list_by_node(self, node_id: str) -> list[SpanEvent]:
        """List all events attached to a node."""
