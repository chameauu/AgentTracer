"""Integration tests for AgentTracer Backend API endpoints.

Inspired by old/backend/tests/integration/test_api.py but adapted for
the single-file backend implementation.
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for /health and /api/v1/health endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_root(self, client: AsyncClient) -> None:
        """Test health check at root /health returns healthy status."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_health_check_v1(self, client: AsyncClient) -> None:
        """Test health check at /api/v1/health returns healthy status."""
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"


class TestRunsAPI:
    """Tests for /api/v1/runs endpoints."""

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client: AsyncClient) -> None:
        """Test listing runs when database is empty."""
        response = await client.get("/api/v1/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_runs_pagination(self, client: AsyncClient) -> None:
        """Test pagination parameters."""
        response = await client.get("/api/v1/runs?limit=10&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent run returns 404."""
        response = await client.get("/api/v1/runs/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_run_tree_not_found(self, client: AsyncClient) -> None:
        """Test getting tree for non-existent run returns 404."""
        response = await client.get("/api/v1/runs/nonexistent-id/tree")

        assert response.status_code == 404


class TestIngestAPI:
    """Tests for /api/v1/ingest/events endpoint."""

    @pytest.mark.asyncio
    async def test_ingest_empty_events(self, client: AsyncClient) -> None:
        """Test ingesting empty event list returns 202."""
        request = {
            "run_id": "test-run-1",
            "run_name": "Test Run",
            "events": [],
        }

        response = await client.post("/api/v1/ingest/events", json=request)

        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 0
        assert data["run_id"] == "test-run-1"

    @pytest.mark.asyncio
    async def test_ingest_span_start(self, client: AsyncClient) -> None:
        """Test ingesting span_start event."""
        request = {
            "run_id": "test-run-2",
            "run_name": "Test Run",
            "events": [
                {
                    "type": "span_start",
                    "data": {
                        "span_id": "span-1",
                        "name": "test_step",
                        "span_type": "step",
                        "timestamp": "2024-01-01T00:00:00Z",
                    },
                }
            ],
        }

        response = await client.post("/api/v1/ingest/events", json=request)

        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 1

    @pytest.mark.asyncio
    async def test_ingest_span_end(self, client: AsyncClient) -> None:
        """Test ingesting span_start followed by span_end."""
        # First, create a span
        await client.post(
            "/api/v1/ingest/events",
            json={
                "run_id": "test-run-3",
                "run_name": "Test Run",
                "events": [
                    {
                        "type": "span_start",
                        "data": {
                            "span_id": "span-2",
                            "name": "test_step",
                            "span_type": "step",
                            "timestamp": "2024-01-01T00:00:00Z",
                        },
                    }
                ],
            },
        )

        # Now, end the span
        response = await client.post(
            "/api/v1/ingest/events",
            json={
                "run_id": "test-run-3",
                "events": [
                    {
                        "type": "span_end",
                        "data": {
                            "span_id": "span-2",
                            "timestamp": "2024-01-01T00:00:05Z",
                        },
                    }
                ],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 1

    @pytest.mark.asyncio
    async def test_ingest_span_event(self, client: AsyncClient) -> None:
        """Test ingesting span_event (input/output/error)."""
        # First create a span
        await client.post(
            "/api/v1/ingest/events",
            json={
                "run_id": "test-run-4",
                "events": [
                    {
                        "type": "span_start",
                        "data": {
                            "span_id": "span-3",
                            "name": "test_step",
                            "span_type": "step",
                            "timestamp": "2024-01-01T00:00:00Z",
                        },
                    }
                ],
            },
        )

        # Add an event (e.g., input)
        response = await client.post(
            "/api/v1/ingest/events",
            json={
                "run_id": "test-run-4",
                "events": [
                    {
                        "type": "span_event",
                        "data": {
                            "span_id": "span-3",
                            "event_type": "input",
                            "timestamp": "2024-01-01T00:00:01Z",
                            "payload": {"query": "hello world"},
                        },
                    }
                ],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["accepted"] == 1

    @pytest.mark.asyncio
    async def test_full_workflow(self, client: AsyncClient) -> None:
        """Test complete workflow: ingest events, list runs, get tree."""
        # 1. Ingest events
        ingest_response = await client.post(
            "/api/v1/ingest/events",
            json={
                "run_id": "full-workflow-test",
                "run_name": "Full Workflow Test",
                "events": [
                    {
                        "type": "span_start",
                        "data": {
                            "span_id": "root-span",
                            "name": "Agent Run",
                            "span_type": "agent_run",
                            "timestamp": "2024-01-01T00:00:00Z",
                        },
                    },
                    {
                        "type": "span_start",
                        "data": {
                            "span_id": "child-span",
                            "parent_id": "root-span",
                            "name": "Step 1",
                            "span_type": "step",
                            "timestamp": "2024-01-01T00:00:01Z",
                        },
                    },
                    {
                        "type": "span_event",
                        "data": {
                            "span_id": "child-span",
                            "event_type": "input",
                            "timestamp": "2024-01-01T00:00:01Z",
                            "payload": {"query": "test"},
                        },
                    },
                    {
                        "type": "span_end",
                        "data": {
                            "span_id": "child-span",
                            "timestamp": "2024-01-01T00:00:02Z",
                        },
                    },
                    {
                        "type": "span_end",
                        "data": {
                            "span_id": "root-span",
                            "timestamp": "2024-01-01T00:00:03Z",
                        },
                    },
                ],
            },
        )

        assert ingest_response.status_code == 202
        assert ingest_response.json()["accepted"] == 5

        # 2. List runs
        list_response = await client.get("/api/v1/runs")
        assert list_response.status_code == 200
        runs = list_response.json()["runs"]
        assert len(runs) >= 1

        # 3. Get run details
        run_id = runs[0]["id"]
        run_response = await client.get(f"/api/v1/runs/{run_id}")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert run_data["name"] == "Full Workflow Test"

        # 4. Get run tree
        tree_response = await client.get(f"/api/v1/runs/{run_id}/tree")
        assert tree_response.status_code == 200
        tree_data = tree_response.json()
        assert tree_data["root"] is not None
        assert tree_data["root"]["name"] == "Agent Run"
        assert len(tree_data["root"]["children"]) == 1
        assert tree_data["root"]["children"][0]["name"] == "Step 1"

    @pytest.mark.asyncio
    async def test_run_auto_creation(self, client: AsyncClient) -> None:
        """Test that runs are auto-created on first event."""
        # Ingest without providing run_name - should auto-create
        response = await client.post(
            "/api/v1/ingest/events",
            json={
                "run_id": "auto-created-run",
                "events": [
                    {
                        "type": "span_start",
                        "data": {
                            "span_id": "span-1",
                            "name": "Test",
                            "span_type": "step",
                            "timestamp": "2024-01-01T00:00:00Z",
                        },
                    }
                ],
            },
        )

        assert response.status_code == 202

        # Verify run was created with auto-generated name
        run_response = await client.get("/api/v1/runs/auto-created-run")
        assert run_response.status_code == 200
        run_data = run_response.json()
        assert run_data["status"] == "running"
        # Default name pattern is "run-{run_id[:8]}"
        assert run_data["name"] == "run-auto-cre"
