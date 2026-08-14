"""End-to-End tests for SDK format validation.

These tests verify that the SDK produces events in the correct format
for the Backend API. They test the format conversion logic in the
AgentTraceSpanExporter.

Inspired by old/sdk/tests/test_e2e.py but adapted for OpenTelemetry.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry.trace import SpanContext

from agent_trace_sdk import (
    AgentTraceSpanExporter,
    init_tracing,
    record_input,
    record_output,
    trace_agent_run,
    trace_span,
)


class TestSDKFormatValidation:
    """Tests that verify SDK produces Backend-compatible format."""

    @pytest.fixture
    def exporter(self):
        """Create an exporter with a mock HTTP client."""
        exporter = AgentTraceSpanExporter(endpoint="http://localhost:8000/api/v1/ingest/events")
        return exporter

    @pytest.mark.asyncio
    async def test_span_start_event_format(self, exporter):
        """Test that span_start event has correct format."""
        # Create a mock OTel span
        span = MagicMock()
        span.context = MagicMock(spec=SpanContext)
        span.context.span_id = 0x1234567890ABCDEF
        span.parent = None
        span.name = "Test Span"
        span.attributes = {"span_type": "agent_run", "model": "gpt-4"}
        span.start_time = 1704067200000000000  # 2024-01-01 00:00:00 UTC
        span.end_time = None
        span.events = []

        # Mock the client and its post method
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        # Patch the async method to return our mock client
        exporter._client = mock_client

        result = exporter.export([span])

        assert result.name == "SUCCESS"

        # Check that the correct payload was sent
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]

        assert "run_id" in payload
        assert "events" in payload

        events = payload["events"]
        span_start_event = events[0]

        assert span_start_event["type"] == "span_start"
        assert "data" in span_start_event
        assert "span_id" in span_start_event["data"]
        assert "name" in span_start_event["data"]
        assert "span_type" in span_start_event["data"]
        assert "timestamp" in span_start_event["data"]

    @pytest.mark.asyncio
    async def test_span_end_event_format(self, exporter):
        """Test that span_end event has correct format."""
        # Create a mock OTel span with end_time
        span = MagicMock()
        span.context = MagicMock(spec=SpanContext)
        span.context.span_id = 0x1234567890ABCDEF
        span.parent = None
        span.name = "Test Span"
        span.attributes = {}
        span.start_time = 1704067200000000000
        span.end_time = 1704067205000000000  # 5 seconds later
        span.events = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        result = exporter.export([span])

        assert result.name == "SUCCESS"

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        events = payload["events"]

        # Should have both span_start and span_end
        assert len(events) == 2
        span_end_event = events[1]

        assert span_end_event["type"] == "span_end"
        assert span_end_event["data"]["span_id"] is not None
        assert span_end_event["data"]["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_span_event_format(self, exporter):
        """Test that span events (input, output, error) have correct format."""
        # Create a mock OTel span with events
        span = MagicMock()
        span.context = MagicMock(spec=SpanContext)
        span.context.span_id = 0x1234567890ABCDEF
        span.parent = None
        span.name = "Test Span"
        span.attributes = {}
        span.start_time = 1704067200000000000
        span.end_time = 1704067205000000000

        # Add an OTel event (like "input" or "output")
        otel_event = MagicMock()
        otel_event.name = "input"
        otel_event.timestamp = 1704067201000000000
        otel_event.attributes = {"query": "hello world"}
        span.events = [otel_event]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        result = exporter.export([span])

        assert result.name == "SUCCESS"

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        events = payload["events"]

        # Should have: span_start, span_end, span_event
        assert len(events) == 3

        # Find the span_event
        span_event = next(e for e in events if e["type"] == "span_event")
        assert span_event["data"]["event_type"] == "input"
        assert span_event["data"]["payload"]["query"] == "hello world"

    @pytest.mark.asyncio
    async def test_run_id_from_first_span(self, exporter):
        """Test that run_id is derived from the first span's span_id."""
        # Create two spans - use string span_id to avoid format issues
        span1 = MagicMock()
        span1.context = MagicMock()
        span1.context.span_id = "1111111111111111"
        span1.parent = None
        span1.name = "Span 1"
        span1.attributes = {}
        span1.start_time = 1704067200000000000
        span1.end_time = None
        span1.events = []

        span2 = MagicMock()
        span2.context = MagicMock()
        span2.context.span_id = "2222222222222222"
        span2.parent = None
        span2.name = "Span 2"
        span2.attributes = {}
        span2.start_time = 1704067200000000000
        span2.end_time = None
        span2.events = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        exporter.export([span1, span2])

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]

        # run_id should come from first span
        assert payload["run_id"] == "1111111111111111"

    @pytest.mark.asyncio
    async def test_parent_id_extraction(self, exporter):
        """Test that parent_id is correctly extracted from parent span."""
        # Create parent span
        parent_span = MagicMock()
        parent_span.context = MagicMock(spec=SpanContext)
        parent_span.context.span_id = 0xAAAAAAAABBBBBBBB
        parent_span.parent = None
        parent_span.name = "Parent Span"
        parent_span.attributes = {"span_type": "agent_run"}
        parent_span.start_time = 1704067200000000000
        parent_span.end_time = None
        parent_span.events = []

        # Create child span with parent
        child_span = MagicMock()
        child_span.context = MagicMock(spec=SpanContext)
        child_span.context.span_id = 0xCCCCCCCCDDDDDDDD
        child_span.parent = MagicMock()
        child_span.parent.span_id = 0xAAAAAAAABBBBBBBB
        child_span.name = "Child Span"
        child_span.attributes = {"span_type": "step"}
        child_span.start_time = 1704067201000000000
        child_span.end_time = None
        child_span.events = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        exporter.export([parent_span, child_span])

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]

        events = payload["events"]
        # Find child span_start event
        child_start = next(
            e for e in events if e["type"] == "span_start" and e["data"]["name"] == "Child Span"
        )

        assert child_start["data"]["parent_id"] == format(0xAAAAAAAABBBBBBBB, "x")

    @pytest.mark.asyncio
    async def test_attributes_preserved(self, exporter):
        """Test that span attributes are preserved in the output."""
        span = MagicMock()
        span.context = MagicMock(spec=SpanContext)
        span.context.span_id = 0x1234567890ABCDEF
        span.parent = None
        span.name = "Test Span"
        span.attributes = {
            "span_type": "agent_run",
            "model": "gpt-4",
            "temperature": 0.7,
            "custom_attr": "value",
        }
        span.start_time = 1704067200000000000
        span.end_time = None
        span.events = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        exporter.export([span])

        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]

        events = payload["events"]
        span_start = events[0]

        # span_type should be extracted, other attributes preserved
        assert span_start["data"]["span_type"] == "agent_run"
        assert span_start["data"]["attributes"]["model"] == "gpt-4"
        assert span_start["data"]["attributes"]["temperature"] == 0.7
        assert span_start["data"]["attributes"]["custom_attr"] == "value"

    @pytest.mark.asyncio
    async def test_run_name_from_agent_run_span(self, exporter):
        """Test that run_name is taken from the agent_run span's name."""
        span = MagicMock()
        span.context = MagicMock(spec=SpanContext)
        span.context.span_id = 0x1234567890ABCDEF
        span.parent = None
        span.name = "my_agent"
        span.attributes = {"span_type": "agent_run"}
        span.start_time = 1704067200000000000
        span.end_time = None
        span.events = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        exporter.export([span])

        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["run_name"] == "my_agent"

    @pytest.mark.asyncio
    async def test_run_name_omitted_without_agent_run_span(self, exporter):
        """Test that run_name is omitted when no agent_run span is present."""
        span = MagicMock()
        span.context = MagicMock(spec=SpanContext)
        span.context.span_id = 0x1234567890ABCDEF
        span.parent = None
        span.name = "Child Span"
        span.attributes = {"span_type": "step"}
        span.start_time = 1704067200000000000
        span.end_time = None
        span.events = []

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        exporter._client = mock_client

        exporter.export([span])

        payload = mock_client.post.call_args.kwargs["json"]
        assert "run_name" not in payload


class TestSDKDecorator:
    """Tests for the @trace_agent_run decorator."""

    def test_decorator_creates_span(self):
        """Test that decorator creates a span."""

        @trace_agent_run(name="test_decorator")
        def my_function():
            return "hello"

        # The function should execute without error
        result = my_function()
        assert result == "hello"

    def test_decorator_uses_function_name(self):
        """Test that decorator uses function name if no name provided."""

        @trace_agent_run()
        def my_agent():
            return "result"

        result = my_agent()
        assert result == "result"

    def test_decorator_injects_span(self):
        """Test that decorator injects span into function kwargs."""
        received_span = None

        @trace_agent_run(name="test_injection")
        def my_function(trace_span=None):
            nonlocal received_span
            received_span = trace_span
            return "done"

        result = my_function()

        assert result == "done"
        assert received_span is not None

    def test_decorator_with_args(self):
        """Test that decorator works with function arguments."""

        @trace_agent_run(name="test_args")
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_decorator_preserves_return_type(self):
        """Test that decorator preserves function return type."""

        @trace_agent_run(name="test_return")
        def get_dict() -> dict:
            return {"key": "value"}

        result = get_dict()
        assert result == {"key": "value"}


class TestTraceSpanDecorator:
    """Tests for the @trace_span decorator (nested spans)."""

    def test_decorator_creates_span(self):
        """Test that the decorator executes the function normally."""

        @trace_span(name="test_span")
        def my_function():
            return "hello"

        result = my_function()
        assert result == "hello"

    def test_decorator_uses_function_name(self):
        """Test that the span uses the function name when no name is given."""

        @trace_span()
        def my_tool():
            return "result"

        assert my_tool() == "result"

    def test_decorator_sets_span_type(self):
        """Test that the span_type attribute is set on the span."""

        @trace_span(name="search", span_type="tool_call")
        def search(trace_span=None):
            return trace_span

        span = search()
        assert span.attributes.get("span_type") == "tool_call"

    def test_decorator_defaults_to_step(self):
        """Test that span_type defaults to 'step'."""

        @trace_span()
        def work(trace_span=None):
            return trace_span

        span = work()
        assert span.attributes.get("span_type") == "step"

    def test_decorator_nests_under_active_span(self):
        """Test that a traced function runs as a child of the active span."""
        from agent_trace_sdk import get_tracer

        tracer = get_tracer()
        with tracer.start_as_current_span("parent"):

            @trace_span(name="child", span_type="tool_call")
            def tool(trace_span=None):
                return trace_span

            span = tool()
        assert span.attributes.get("span_type") == "tool_call"

    def test_decorator_with_args(self):
        """Test that the decorator works with function arguments."""

        @trace_span(name="add")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_decorator_preserves_return_type(self):
        """Test that the decorator preserves the return value."""

        @trace_span(name="get_dict")
        def get_dict() -> dict:
            return {"key": "value"}

        assert get_dict() == {"key": "value"}


class TestSpanEvents:
    """Tests for the record_input / record_output helpers."""

    def test_record_input_adds_input_event(self):
        """Test that record_input adds an 'input' event to the span."""

        @trace_span(name="fn")
        def fn(trace_span=None):
            record_input("hello")
            return trace_span

        span = fn()
        assert [(e.name, dict(e.attributes)) for e in span.events] == [
            ("input", {"value": "hello"})
        ]

    def test_record_output_spreads_dict_attributes(self):
        """Test that dict values become the event attributes directly."""

        @trace_span(name="fn")
        def fn(trace_span=None):
            record_output({"result": 42})
            return trace_span

        span = fn()
        assert [(e.name, dict(e.attributes)) for e in span.events] == [("output", {"result": 42})]

    def test_record_event_is_noop_without_active_span(self):
        """Test that the helpers do nothing when no span is recording."""
        record_input("x")
        record_output("y")

    def test_record_output_nested_dict_payload_is_json_encoded(self):
        """Nested non-primitive values are JSON-encoded, not dropped."""

        @trace_span(name="fn")
        def fn(trace_span=None):
            record_output({"steps": [{"tool": "search", "result": {"hits": 3}}]})
            return trace_span

        span = fn()
        events = [(e.name, dict(e.attributes)) for e in span.events]
        assert events[0][0] == "output"
        assert json.loads(events[0][1]["steps"]) == [{"tool": "search", "result": {"hits": 3}}]

    def test_record_input_list_of_primitives_kept_as_list(self):
        """Sequences of primitives stay as sequences."""

        @trace_span(name="fn")
        def fn(trace_span=None):
            record_input({"plan": ["search_web", "get_time"]})
            return trace_span

        span = fn()
        attrs = [dict(e.attributes) for e in span.events]
        assert list(attrs[0]["plan"]) == ["search_web", "get_time"]


class TestSDKInit:
    """Tests for init_tracing and get_tracer."""

    def test_init_tracing_sets_provider(self):
        """Test that init_tracing sets up the tracer provider."""
        # This should not raise an error
        init_tracing(service_name="test-service")

        # Get the tracer - should work without error
        from agent_trace_sdk.setup import get_tracer

        tracer = get_tracer()
        assert tracer is not None

    def test_get_tracer_returns_default(self):
        """Test that get_tracer returns a default if not initialized."""
        from agent_trace_sdk.setup import get_tracer

        tracer = get_tracer()
        assert tracer is not None
