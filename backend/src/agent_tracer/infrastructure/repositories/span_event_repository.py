"""SQLAlchemy implementation of ISpanEventRepository."""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ...domain.entities import SpanEvent
from ...domain.interfaces import ISpanEventRepository
from ..models import SpanEventModel
def _entity_to_model(event: SpanEvent) -> SpanEventModel:
    """Convert a domain SpanEvent to an ORM row."""
    return SpanEventModel(
        id=event.id,
        node_id=event.node_id,
        event_type=event.event_type,
        timestamp=event.timestamp.isoformat(),
        payload_json=json.dumps(event.payload),
    )
def _model_to_entity(model: SpanEventModel) -> SpanEvent:
    """Convert an ORM row back to a domain SpanEvent."""
    return SpanEvent(
        id=model.id,
        node_id=model.node_id,
        event_type=model.event_type,
        timestamp=datetime.fromisoformat(model.timestamp),
        payload=json.loads(model.payload_json or "{}"),
    )
class SqlSpanEventRepository(ISpanEventRepository):
    """Async SQLAlchemy-backed span event repository."""
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
    async def save(self, event: SpanEvent) -> None:
        async with self._session_factory() as session:
            await session.merge(_entity_to_model(event))
            await session.commit()
    async def list_by_node(self, node_id: str) -> list[SpanEvent]:
        async with self._session_factory() as session:
            stmt = select(SpanEventModel).where(
                SpanEventModel.node_id == node_id
            )
            rows = await session.scalars(stmt)
            return [_model_to_entity(m) for m in rows]