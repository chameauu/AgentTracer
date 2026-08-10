"""SQLAlchemy implementation of ITraceNodeRepository."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...domain.entities import TraceNode
from ...domain.interfaces import ITraceNodeRepository
from ...domain.value_objects import SpanType
from ..models import TraceNodeModel


def _entity_to_model(node: TraceNode) -> TraceNodeModel:
    """Convert a domain TraceNode to an ORM row (children not persisted)."""
    return TraceNodeModel(
        id=node.id,
        run_id=node.run_id,
        parent_id=node.parent_id,
        name=node.name,
        span_type=node.span_type.value,
        started_at=node.started_at.isoformat(),
        ended_at=node.ended_at.isoformat() if node.ended_at else None,
        attributes_json=json.dumps(node.attributes),
    )


def _model_to_entity(model: TraceNodeModel) -> TraceNode:
    """Convert an ORM row back to a domain TraceNode (children empty)."""
    return TraceNode(
        id=model.id,
        run_id=model.run_id,
        parent_id=model.parent_id,
        name=model.name,
        span_type=SpanType(model.span_type),
        started_at=datetime.fromisoformat(model.started_at),
        ended_at=datetime.fromisoformat(model.ended_at) if model.ended_at else None,
        attributes=json.loads(model.attributes_json or "{}"),
    )


class SqlTraceNodeRepository(ITraceNodeRepository):
    """Async SQLAlchemy-backed trace node repository."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, node: TraceNode) -> None:
        async with self._session_factory() as session:
            await session.merge(_entity_to_model(node))
            await session.commit()

    async def get(self, node_id: str) -> TraceNode | None:
        async with self._session_factory() as session:
            model = await session.get(TraceNodeModel, node_id)
            return _model_to_entity(model) if model else None

    async def list_by_run(self, run_id: str) -> list[TraceNode]:
        async with self._session_factory() as session:
            stmt = select(TraceNodeModel).where(TraceNodeModel.run_id == run_id)
            rows = await session.scalars(stmt)
            return [_model_to_entity(m) for m in rows]
