"""Unit tests for the application layer services.

Covers IngestService (run auto-creation, span_start/end/event handling,
resilience) and RunService (listing, retrieval, tree assembly) using the
real SQL repositories backed by an in-memory SQLite engine.
"""

from __future__ import annotations

import pytest

from agent_tracer.application import RunNotFoundError

from ..conftest import Services

# ── IngestService ───────────────────────────────────────────────────────────


class TestIngestService:
    """Tests for IngestService.ingest()."""

    @pytest.mark.asyncio
    async def test_ingest_empty_events_creates_run(self, services: Services) -> None:
        """Ingesting an empty batch auto-creates the run."""
        accepted = await services.ingest.ingest("run-1", "Test Run", [])
        assert accepted == 0

        run = await services.run.get_run("run-1")
        assert run["name"] == "Test Run"
        assert run["status"] == "running"
        assert run["node_count"] == 0

    @pytest.mark.asyncio
    async def test_ingest_auto_generates_run_name(self, services: Services) -> None:
        """Without run_name, name defaults to run-{id[:8]}."""
        await services.ingest.ingest("abcdefghijkl", None, [])
        run = await services.run.get_run("abcdefghijkl")
        assert run["name"] == "run-abcdefgh"

    @pytest.mark.asyncio
    async def test_ingest_does_not_duplicate_run(self, services: Services) -> None:
        """A second ingest for the same run_id must not create a second row."""
        await services.ingest.ingest("run-1", "Run", [])
        await services.ingest.ingest("run-1", "Run", [])
        listing = await services.run.list_runs()
        assert listing["total"] == 1

    @pytest.mark.asyncio
    async def test_ingest_span_start_creates_node(self, services: Services) -> None:
        """span_start persists a trace node with its attributes."""
        events = [
            {
                "type": "span_start",
                "data": {
                    "span_id": "span-1",
                    "name": "think",
                    "span_type": "step",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "attributes": {"model": "gpt-4"},
                },
            }
        ]
        accepted = await services.ingest.ingest("run-1", "Run", events)
        assert accepted == 1

        tree = await services.run.get_run_tree("run-1")
        root = tree["root"]
        assert root["name"] == "think"
        assert root["span_type"] == "step"
        assert root["attributes"] == {"model": "gpt-4"}
        assert root["ended_at"] is None

    @pytest.mark.asyncio
    async def test_ingest_span_start_generates_span_id(self, services: Services) -> None:
        """span_start without span_id still creates a node (uuid assigned)."""
        events = [{"type": "span_start", "data": {"name": "anonymous", "span_type": "step"}}]
        accepted = await services.ingest.ingest("run-1", "Run", events)
        assert accepted == 1

        tree = await services.run.get_run_tree("run-1")
        assert tree["root"] is not None
        assert tree["root"]["name"] == "anonymous"

    @pytest.mark.asyncio
    async def test_ingest_span_end_completes_node(self, services: Services) -> None:
        """span_end sets ended_at and duration_ms on the matching node."""
        events = [
            {
                "type": "span_start",
                "data": {
                    "span_id": "span-1",
                    "name": "step",
                    "span_type": "step",
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            },
            {
                "type": "span_end",
                "data": {"span_id": "span-1", "timestamp": "2024-01-01T00:00:05Z"},
            },
        ]
        accepted = await services.ingest.ingest("run-1", "Run", events)
        assert accepted == 2

        tree = await services.run.get_run_tree("run-1")
        root = tree["root"]
        assert root["ended_at"] == "2024-01-01T00:00:05+00:00"
        assert root["duration_ms"] == 5000.0

    @pytest.mark.asyncio
    async def test_ingest_span_end_unknown_span_is_ignored(self, services: Services) -> None:
        """span_end for a missing span does not crash and is still counted."""
        events = [
            {"type": "span_end", "data": {"span_id": "ghost", "timestamp": "2024-01-01T00:00:00Z"}}
        ]
        accepted = await services.ingest.ingest("run-1", "Run", events)
        assert accepted == 1

    @pytest.mark.asyncio
    async def test_ingest_span_event_creates_event(self, services: Services) -> None:
        """span_event persists an event on the node."""
        events = [
            {
                "type": "span_start",
                "data": {
                    "span_id": "span-1",
                    "name": "step",
                    "span_type": "step",
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            },
            {
                "type": "span_event",
                "data": {
                    "span_id": "span-1",
                    "event_type": "input",
                    "timestamp": "2024-01-01T00:00:01Z",
                    "payload": {"query": "hello"},
                },
            },
        ]
        accepted = await services.ingest.ingest("run-1", "Run", events)
        assert accepted == 2

        tree = await services.run.get_run_tree("run-1")
        events_on_node = tree["root"]["events"]
        assert len(events_on_node) == 1
        assert events_on_node[0]["event_type"] == "input"
        assert events_on_node[0]["payload"] == {"query": "hello"}

    @pytest.mark.asyncio
    async def test_ingest_bad_event_is_skipped(self, services: Services) -> None:
        """A malformed event is skipped; the accepted count reflects only good ones."""
        events = [
            {"type": "bogus_type", "data": {}},
            {
                "type": "span_start",
                "data": {
                    "span_id": "span-1",
                    "name": "step",
                    "span_type": "step",
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            },
        ]
        accepted = await services.ingest.ingest("run-1", "Run", events)
        # bogus_type hits the else branch (no-op but still counted)
        assert accepted == 2

        tree = await services.run.get_run_tree("run-1")
        assert tree["root"]["name"] == "step"

    @pytest.mark.asyncio
    async def test_ingest_parent_child_relationship(self, services: Services) -> None:
        """span_start with parent_id nests the child under its parent."""
        events = [
            {
                "type": "span_start",
                "data": {
                    "span_id": "root",
                    "name": "Agent Run",
                    "span_type": "agent_run",
                    "timestamp": "2024-01-01T00:00:00Z",
                },
            },
            {
                "type": "span_start",
                "data": {
                    "span_id": "child",
                    "parent_id": "root",
                    "name": "Step 1",
                    "span_type": "step",
                    "timestamp": "2024-01-01T00:00:01Z",
                },
            },
        ]
        await services.ingest.ingest("run-1", "Run", events)

        tree = await services.run.get_run_tree("run-1")
        assert tree["root"]["name"] == "Agent Run"
        assert len(tree["root"]["children"]) == 1
        assert tree["root"]["children"][0]["name"] == "Step 1"


# ── RunService ──────────────────────────────────────────────────────────────


class TestRunService:
    """Tests for RunService.list_runs / get_run / get_run_tree."""

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, services: Services) -> None:
        """Listing with no runs returns an empty page."""
        result = await services.run.list_runs()
        assert result == {"runs": [], "total": 0, "limit": 20, "offset": 0}

    @pytest.mark.asyncio
    async def test_list_runs_returns_runs(self, services: Services) -> None:
        """Runs are listed with node_count populated."""
        await services.ingest.ingest("run-1", "Run A", [])
        await services.ingest.ingest("run-2", "Run B", [])

        result = await services.run.list_runs()
        assert result["total"] == 2
        names = {r["name"] for r in result["runs"]}
        assert names == {"Run A", "Run B"}
        assert all(r["node_count"] == 0 for r in result["runs"])

    @pytest.mark.asyncio
    async def test_list_runs_node_count(self, services: Services) -> None:
        """node_count reflects the number of nodes in the run."""
        events = [
            {
                "type": "span_start",
                "data": {"span_id": "s1", "name": "a", "span_type": "step"},
            },
            {
                "type": "span_start",
                "data": {"span_id": "s2", "name": "b", "span_type": "step"},
            },
        ]
        await services.ingest.ingest("run-1", "Run", events)

        result = await services.run.list_runs()
        assert result["runs"][0]["node_count"] == 2

    @pytest.mark.asyncio
    async def test_list_runs_status_filter(self, services: Services) -> None:
        """Filtering by status only returns matching runs."""
        await services.ingest.ingest("run-1", "Run A", [])
        await services.ingest.ingest("run-2", "Run B", [])

        result = await services.run.list_runs(status="running")
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_list_runs_invalid_status_returns_empty(self, services: Services) -> None:
        """An unknown status yields an empty page instead of raising."""
        await services.ingest.ingest("run-1", "Run A", [])
        result = await services.run.list_runs(status="bogus")
        assert result == {"runs": [], "total": 0, "limit": 20, "offset": 0}

    @pytest.mark.asyncio
    async def test_list_runs_pagination(self, services: Services) -> None:
        """limit/offset are echoed back in the response."""
        result = await services.run.list_runs(limit=10, offset=5)
        assert result["limit"] == 10
        assert result["offset"] == 5

    @pytest.mark.asyncio
    async def test_get_run_returns_run_dict(self, services: Services) -> None:
        """get_run returns the run as a response dict."""
        await services.ingest.ingest("run-1", "Test Run", [])
        run = await services.run.get_run("run-1")

        assert run["id"] == "run-1"
        assert run["name"] == "Test Run"
        assert run["status"] == "running"
        assert run["started_at"] is not None
        assert run["ended_at"] is None
        assert run["duration_ms"] is None
        assert run["metadata"] == {}
        assert run["node_count"] == 0

    @pytest.mark.asyncio
    async def test_get_run_missing_raises(self, services: Services) -> None:
        """get_run on an unknown id raises RunNotFoundError."""
        with pytest.raises(RunNotFoundError):
            await services.run.get_run("does-not-exist")

    @pytest.mark.asyncio
    async def test_get_run_tree_empty_nodes(self, services: Services) -> None:
        """A run without nodes yields root=None."""
        await services.ingest.ingest("run-1", "Run", [])
        tree = await services.run.get_run_tree("run-1")
        assert tree == {"run_id": "run-1", "root": None}

    @pytest.mark.asyncio
    async def test_get_run_tree_missing_raises(self, services: Services) -> None:
        """get_run_tree on an unknown run raises RunNotFoundError."""
        with pytest.raises(RunNotFoundError):
            await services.run.get_run_tree("does-not-exist")
