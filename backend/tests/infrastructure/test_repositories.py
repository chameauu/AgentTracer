"""Integration tests for the SQLAlchemy infrastructure repositories.

Uses an in-memory SQLite database with StaticPool so every session
shares the same connection (and therefore the same in-memory DB).
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from agent_tracer.domain.entities import AgentRun, SpanEvent, TraceNode
from agent_tracer.domain.value_objects import RunStatus, SpanType
from agent_tracer.infrastructure.db import create_session_factory
from agent_tracer.infrastructure.models import Base
from agent_tracer.infrastructure.repositories import (
    SqlRunRepository,
    SqlSpanEventRepository,
    SqlTraceNodeRepository,
)


def _utc(y: int, mo: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


@pytest_asyncio.fixture(scope="function")
async def repos():
    """Create in-memory DB + repositories for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    yield (
        SqlRunRepository(factory),
        SqlTraceNodeRepository(factory),
        SqlSpanEventRepository(factory),
    )
    await engine.dispose()


class TestRunRepository:
    """SqlRunRepository: save/get/list/count."""

    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self, repos) -> None:
        run_repo, _, _ = repos
        run = AgentRun.create(name="my-agent", metadata={"env": "test"})
        await run_repo.save(run)

        fetched = await run_repo.get(run.id)
        assert fetched is not None
        assert fetched.name == "my-agent"
        assert fetched.status == RunStatus.RUNNING
        assert fetched.metadata == {"env": "test"}
        assert fetched.started_at == run.started_at

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, repos) -> None:
        run_repo, _, _ = repos
        assert await run_repo.get("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_save_upserts(self, repos) -> None:
        run_repo, _, _ = repos
        run = AgentRun.create(name="my-agent")
        await run_repo.save(run)

        completed = run.complete()
        await run_repo.save(completed)

        fetched = await run_repo.get(run.id)
        assert fetched is not None
        assert fetched.status == RunStatus.COMPLETED
        assert fetched.ended_at == completed.ended_at

    @pytest.mark.asyncio
    async def test_list_newest_first(self, repos) -> None:
        run_repo, _, _ = repos
        older = AgentRun(
            id="r-older",
            name="older",
            status=RunStatus.RUNNING,
            started_at=_utc(2026, 1, 1, 0, 0, 1),
            created_at=_utc(2026, 1, 1, 0, 0, 1),
            updated_at=_utc(2026, 1, 1, 0, 0, 1),
        )
        newer = AgentRun(
            id="r-newer",
            name="newer",
            status=RunStatus.RUNNING,
            started_at=_utc(2026, 1, 1, 0, 0, 2),
            created_at=_utc(2026, 1, 1, 0, 0, 2),
            updated_at=_utc(2026, 1, 1, 0, 0, 2),
        )
        await run_repo.save(older)
        await run_repo.save(newer)

        runs = await run_repo.list()
        assert [r.id for r in runs] == ["r-newer", "r-older"]

    @pytest.mark.asyncio
    async def test_list_filters_by_status(self, repos) -> None:
        run_repo, _, _ = repos
        running = AgentRun.create(name="a")
        completed = AgentRun.create(name="b").complete()
        await run_repo.save(running)
        await run_repo.save(completed)

        running_list = await run_repo.list(status=RunStatus.RUNNING)
        completed_list = await run_repo.list(status=RunStatus.COMPLETED)
        assert [r.id for r in running_list] == [running.id]
        assert [r.id for r in completed_list] == [completed.id]

    @pytest.mark.asyncio
    async def test_list_pagination(self, repos) -> None:
        run_repo, _, _ = repos
        for i in range(5):
            run = AgentRun(
                id=f"r{i}",
                name=f"run-{i}",
                status=RunStatus.RUNNING,
                started_at=_utc(2026, 1, 1, 0, 0, i),
                created_at=_utc(2026, 1, 1, 0, 0, i),
                updated_at=_utc(2026, 1, 1, 0, 0, i),
            )
            await run_repo.save(run)

        page = await run_repo.list(limit=2, offset=1)
        # newest first: r4, r3, r2, r1, r0 -> offset 1, limit 2 -> [r3, r2]
        assert [r.id for r in page] == ["r3", "r2"]

    @pytest.mark.asyncio
    async def test_count_all_and_by_status(self, repos) -> None:
        run_repo, _, _ = repos
        await run_repo.save(AgentRun.create(name="a"))
        await run_repo.save(AgentRun.create(name="b"))
        await run_repo.save(AgentRun.create(name="c").complete())

        assert await run_repo.count() == 3
        assert await run_repo.count(status=RunStatus.RUNNING) == 2
        assert await run_repo.count(status=RunStatus.COMPLETED) == 1


class TestTraceNodeRepository:
    """SqlTraceNodeRepository: save/get/list_by_run."""

    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self, repos) -> None:
        _, node_repo, _ = repos
        root = TraceNode.create(run_id="r1", name="root", span_type=SpanType.AGENT_RUN)
        child = TraceNode.create(
            run_id="r1", name="step", span_type=SpanType.STEP, parent_id=root.id
        )
        await node_repo.save(root)
        await node_repo.save(child)

        fetched = await node_repo.get(child.id)
        assert fetched is not None
        assert fetched.name == "step"
        assert fetched.parent_id == root.id
        assert fetched.span_type == SpanType.STEP
        assert fetched.attributes == {}

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, repos) -> None:
        _, node_repo, _ = repos
        assert await node_repo.get("does-not-exist") is None

    @pytest.mark.asyncio
    async def test_list_by_run(self, repos) -> None:
        _, node_repo, _ = repos
        for i in range(3):
            node = TraceNode.create(run_id="r1", name=f"n{i}", span_type=SpanType.STEP)
            await node_repo.save(node)
        other = TraceNode.create(run_id="r2", name="other", span_type=SpanType.STEP)
        await node_repo.save(other)

        nodes = await node_repo.list_by_run("r1")
        assert len(nodes) == 3
        assert all(n.run_id == "r1" for n in nodes)

    @pytest.mark.asyncio
    async def test_children_not_persisted(self, repos) -> None:
        _, node_repo, _ = repos
        root = TraceNode.create(run_id="r1", name="root", span_type=SpanType.AGENT_RUN)
        child = TraceNode.create(
            run_id="r1", name="step", span_type=SpanType.STEP, parent_id=root.id
        )
        root.add_child(child)
        await node_repo.save(root)

        fetched = await node_repo.get(root.id)
        assert fetched is not None
        assert fetched.children == []  # tree built by TreeBuilder, not ORM


class TestSpanEventRepository:
    """SqlSpanEventRepository: save/list_by_node."""

    @pytest.mark.asyncio
    async def test_save_and_list_by_node_roundtrip(self, repos) -> None:
        _, _, event_repo = repos
        event = SpanEvent.create(
            node_id="n1",
            event_type="tool_call",
            payload={"input": "hi", "output": "there"},
        )
        await event_repo.save(event)

        events = await event_repo.list_by_node("n1")
        assert len(events) == 1
        assert events[0].event_type == "tool_call"
        assert events[0].payload == {"input": "hi", "output": "there"}
        assert events[0].timestamp == event.timestamp

    @pytest.mark.asyncio
    async def test_list_by_node_empty(self, repos) -> None:
        _, _, event_repo = repos
        assert await event_repo.list_by_node("nope") == []

    @pytest.mark.asyncio
    async def test_list_by_node_scoped_to_node(self, repos) -> None:
        _, _, event_repo = repos
        e1 = SpanEvent.create(node_id="n1", event_type="a")
        e2 = SpanEvent.create(node_id="n2", event_type="b")
        await event_repo.save(e1)
        await event_repo.save(e2)

        events = await event_repo.list_by_node("n1")
        assert [e.id for e in events] == [e1.id]
