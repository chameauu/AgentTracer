"""Application service for querying runs and trace trees."""

from __future__ import annotations

from ...domain.entities import AgentRun, TraceNode
from ...domain.interfaces import (
    IRunRepository,
    ISpanEventRepository,
    ITraceNodeRepository,
)
from ...domain.services import TreeBuilder
from ...domain.value_objects import RunStatus


class RunNotFoundError(Exception):
    """Raised when a run does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Run {run_id} not found")
        self.run_id = run_id


class RunService:
    """Query orchestration for runs and trees."""

    def __init__(
        self,
        run_repo: IRunRepository,
        node_repo: ITraceNodeRepository,
        event_repo: ISpanEventRepository,
    ) -> None:
        self._runs = run_repo
        self._nodes = node_repo
        self._events = event_repo

    async def list_runs(self, limit: int = 20, offset: int = 0, status: str | None = None) -> dict:
        status_enum: RunStatus | None = None
        if status is not None:
            try:
                status_enum = RunStatus(status)
            except ValueError:
                return {"runs": [], "total": 0, "limit": limit, "offset": offset}
        runs = await self._runs.list(limit=limit, offset=offset, status=status_enum)
        total = await self._runs.count(status=status_enum)
        return {
            "runs": [await self._run_dict(r) for r in runs],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_run(self, run_id: str) -> dict:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return await self._run_dict(run)

    async def get_run_tree(self, run_id: str) -> dict:
        run = await self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        nodes = await self._nodes.list_by_run(run_id)
        if not nodes:
            return {"run_id": run_id, "root": None}
        events_map: dict[str, list] = {}
        for node in nodes:
            events_map[node.id] = [
                self._event_dict(e) for e in await self._events.list_by_node(node.id)
            ]
        roots = TreeBuilder.build_tree(nodes)
        root = roots[0] if roots else None
        return {
            "run_id": run_id,
            "root": self._node_dict(root, events_map) if root else None,
        }

    async def _run_dict(self, run: AgentRun) -> dict:
        node_count = len(await self._nodes.list_by_run(run.id))
        return {
            "id": run.id,
            "name": run.name,
            "status": run.status.value,
            "started_at": run.started_at.isoformat(),
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "duration_ms": run.duration_ms,
            "metadata": run.metadata,
            "node_count": node_count,
        }

    def _node_dict(self, node: TraceNode, events_map: dict[str, list]) -> dict:
        return {
            "id": node.id,
            "name": node.name,
            "span_type": node.span_type.value,
            "started_at": node.started_at.isoformat(),
            "ended_at": node.ended_at.isoformat() if node.ended_at else None,
            "duration_ms": node.duration_ms,
            "attributes": node.attributes,
            "children": [self._node_dict(c, events_map) for c in node.children],
            "events": events_map.get(node.id, []),
        }

    def _event_dict(self, event) -> dict:
        return {
            "id": event.id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }
