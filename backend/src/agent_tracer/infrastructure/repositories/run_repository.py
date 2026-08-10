"""SQLAlchemy implementation of IRunRepository."""
from __future__ import annotations
import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ...domain.entities import AgentRun
from ...domain.interfaces import IRunRepository
from ...domain.value_objects import RunStatus
from ..models import RunModel
def _entity_to_model(run: AgentRun) -> RunModel:
    """Convert a domain AgentRun to an ORM row."""
    return RunModel(
        id=run.id,
        name=run.name,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        ended_at=run.ended_at.isoformat() if run.ended_at else None,
        metadata_json=json.dumps(run.metadata),
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )
def _model_to_entity(model: RunModel) -> AgentRun:
    """Convert an ORM row back to a domain AgentRun."""
    return AgentRun(
        id=model.id,
        name=model.name,
        status=RunStatus(model.status),
        started_at=datetime.fromisoformat(model.started_at),
        ended_at=datetime.fromisoformat(model.ended_at) if model.ended_at else None,
        metadata=json.loads(model.metadata_json or "{}"),
        created_at=datetime.fromisoformat(model.created_at),
        updated_at=datetime.fromisoformat(model.updated_at),
    )
class SqlRunRepository(IRunRepository):
    """Async SQLAlchemy-backed run repository."""
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
    async def save(self, run: AgentRun) -> None:
        async with self._session_factory() as session:
            await session.merge(_entity_to_model(run))
            await session.commit()
    async def get(self, run_id: str) -> AgentRun | None:
        async with self._session_factory() as session:
            model = await session.get(RunModel, run_id)
            return _model_to_entity(model) if model else None
    async def list(
        self, limit: int = 20, offset: int = 0, status: RunStatus | None = None
    ) -> list[AgentRun]:
        async with self._session_factory() as session:
            stmt = select(RunModel).order_by(RunModel.created_at.desc())
            if status is not None:
                stmt = stmt.where(RunModel.status == status.value)
            stmt = stmt.limit(limit).offset(offset)
            rows = await session.scalars(stmt)
            return [_model_to_entity(m) for m in rows]
    async def count(self, status: RunStatus | None = None) -> int:
        async with self._session_factory() as session:
            stmt = select(RunModel.id)
            if status is not None:
                stmt = stmt.where(RunModel.status == status.value)
            rows = await session.scalars(stmt)
            return len(rows.all())