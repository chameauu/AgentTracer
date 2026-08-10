"""Unit tests for the domain layer (value objects, entities, services).

Pure unit tests: no DB, no HTTP, no fixtures. They lock down the
behavior of the Clean Architecture domain layer.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from agent_tracer.domain.entities import AgentRun, SpanEvent, TraceNode
from agent_tracer.domain.interfaces import MockClock
from agent_tracer.domain.services import TreeBuilder
from agent_tracer.domain.value_objects import RunStatus, SpanType


class TestAgentRun:
    """AgentRun lifecycle: create -> complete/fail."""

    def test_create_sets_running_status(self) -> None:
        run = AgentRun.create(name="my-agent")
        assert run.status == RunStatus.RUNNING
        assert run.name == "my-agent"
        assert run.id

    def test_complete_returns_new_instance(self) -> None:
        run = AgentRun.create(name="my-agent")
        completed = run.complete()
        assert completed.status == RunStatus.COMPLETED
        # frozen: original unchanged, new object returned
        assert run.status == RunStatus.RUNNING
        assert completed is not run

    def test_fail_sets_failed_status(self) -> None:
        run = AgentRun.create(name="my-agent")
        assert run.fail().status == RunStatus.FAILED

    def test_duration_ms_with_mock_clock(self) -> None:
        clock = MockClock(datetime(2026, 1, 1, tzinfo=UTC))
        run = AgentRun(
            id="r1",
            name="my-agent",
            status=RunStatus.RUNNING,
            started_at=clock.utcnow(),
        )
        completed = run.complete(ended_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC))
        assert completed.duration_ms == 5000.0

    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            AgentRun(
                id="",
                name="x",
                status=RunStatus.RUNNING,
                started_at=datetime.now(UTC),
            )

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            AgentRun(
                id="r1",
                name="",
                status=RunStatus.RUNNING,
                started_at=datetime.now(UTC),
            )

    def test_ended_at_before_started_at_rejected(self) -> None:
        with pytest.raises(ValueError):
            AgentRun(
                id="r1",
                name="x",
                status=RunStatus.COMPLETED,
                started_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            )


class TestTraceNode:
    """TraceNode: create, link, complete."""

    def test_create_sets_parent(self) -> None:
        node = TraceNode.create(run_id="r1", name="step", span_type=SpanType.STEP, parent_id="root")
        assert node.parent_id == "root"
        assert node.is_root() is False

    def test_root_when_no_parent(self) -> None:
        node = TraceNode.create(run_id="r1", name="root", span_type=SpanType.AGENT_RUN)
        assert node.is_root() is True

    def test_add_child_mutates_children(self) -> None:
        root = TraceNode.create(run_id="r1", name="root", span_type=SpanType.AGENT_RUN)
        child = TraceNode.create(run_id="r1", name="step", span_type=SpanType.STEP)
        root.add_child(child)
        assert len(root.children) == 1
        assert root.children[0] is child

    def test_complete_stamps_ended_at(self) -> None:
        node = TraceNode.create(run_id="r1", name="root", span_type=SpanType.AGENT_RUN)
        assert node.ended_at is None
        node.complete()
        assert node.ended_at is not None


class TestSpanEvent:
    """SpanEvent: immutable value object."""

    def test_frozen(self) -> None:
        event = SpanEvent(
            id="e1",
            node_id="n1",
            event_type="tool_call",
            timestamp=datetime.now(UTC),
            payload={},
        )
        with pytest.raises(FrozenInstanceError):
            event.event_type = "changed"  # type: ignore[misc]


class TestTreeBuilder:
    """TreeBuilder: tree assembly and traversal."""

    def _make_nodes(self) -> list[TraceNode]:
        root = TraceNode.create(run_id="r1", name="root", span_type=SpanType.AGENT_RUN)
        step = TraceNode.create(
            run_id="r1", name="step", span_type=SpanType.STEP, parent_id=root.id
        )
        tool = TraceNode.create(
            run_id="r1", name="tool", span_type=SpanType.TOOL_CALL, parent_id=step.id
        )
        return [step, root, tool]  # intentionally shuffled input

    def test_build_tree_links_children(self) -> None:
        roots = TreeBuilder.build_tree(self._make_nodes())
        assert len(roots) == 1
        assert len(roots[0].children) == 1
        assert roots[0].children[0].children[0].name == "tool"

    def test_build_tree_handles_shuffled_input(self) -> None:
        roots = TreeBuilder.build_tree(self._make_nodes())
        # root has no parent -> is the single root regardless of order
        assert roots[0].name == "root"

    def test_build_tree_orphan_becomes_root(self) -> None:
        orphan = TraceNode.create(
            run_id="r1", name="lost", span_type=SpanType.STEP, parent_id="missing"
        )
        roots = TreeBuilder.build_tree([orphan])
        assert len(roots) == 1
        assert roots[0].name == "lost"

    def test_flatten_tree_dfs_order(self) -> None:
        roots = TreeBuilder.build_tree(self._make_nodes())
        names = [n.name for n in TreeBuilder.flatten_tree(roots)]
        assert names == ["root", "step", "tool"]

    def test_find_node(self) -> None:
        roots = TreeBuilder.build_tree(self._make_nodes())
        found = TreeBuilder.find_node(roots, roots[0].children[0].children[0].id)
        assert found is not None and found.name == "tool"
        assert TreeBuilder.find_node(roots, "nope") is None

    def test_count_nodes(self) -> None:
        roots = TreeBuilder.build_tree(self._make_nodes())
        assert TreeBuilder.count_nodes(roots) == 3

    def test_count_by_type(self) -> None:
        roots = TreeBuilder.build_tree(self._make_nodes())
        counts = TreeBuilder.count_by_type(roots)
        assert counts == {"agent_run": 1, "step": 1, "tool_call": 1}


class TestMockClock:
    """MockClock returns the fixed time."""

    def test_fixed_time(self) -> None:
        fixed = datetime(2026, 1, 1, tzinfo=UTC)
        clock = MockClock(fixed)
        assert clock.utcnow() == fixed
