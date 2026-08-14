"""Setup and initialization for OpenTelemetry-based AgentTracer SDK."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter

from .exporter import AgentTraceSpanExporter
from .processor import RetryBatchSpanProcessor

P = ParamSpec("P")
R = TypeVar("R")

_tracer: trace.Tracer | None = None


_DEFAULT_ENDPOINT = "http://localhost:8000/api/v1/ingest/events"


def init_tracing(
    service_name: str = "agent-tracer",
    endpoint: str | None = None,
    exporter: SpanExporter | None = None,
) -> None:
    """Initialize OpenTelemetry tracing with the AgentTrace exporter.

    Call this once at application startup to set up the global tracer provider.

    Args:
        service_name: Name of your service/agent (used as resource attribute).
        endpoint: URL of the AgentTrace backend ingest endpoint.
            Defaults to http://localhost:8000/api/v1/ingest/events.
        exporter: Optional SpanExporter to use instead of the default HTTP
            exporter (e.g. ConsoleSpanExporter(mode="json") for debugging).
    """
    global _tracer

    if endpoint is None:
        endpoint = _DEFAULT_ENDPOINT

    provider = TracerProvider()
    if exporter is None:
        exporter = AgentTraceSpanExporter(endpoint=endpoint)
    processor = RetryBatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    # Set the global tracer provider
    trace.set_tracer_provider(provider)

    # Create a named tracer for this service
    _tracer = trace.get_tracer(service_name)


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance.

    Returns:
        The global tracer. If init_tracing() hasn't been called,
        a default tracer is returned (uses OTel's global provider).
    """
    if _tracer is not None:
        return _tracer
    return trace.get_tracer("agent-tracer")


def shutdown_tracing() -> None:
    """Shutdown the tracer provider, flushing any pending spans.

    This should be called at the end of your application to ensure
    all buffered spans are exported to the backend before exit.
    """
    global _tracer
    provider = trace.get_tracer_provider()
    if hasattr(provider, "shutdown"):
        provider.shutdown()
    _tracer = None


def trace_agent_run(
    name: str | None = None,
    endpoint: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that traces a function as an agent run using OpenTelemetry.

    If init_tracing() hasn't been called yet, it will be called automatically
    with default settings.

    Usage:
        @trace_agent_run(name="my_agent")
        def my_agent(input: str) -> str:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        run_name = name or func.__name__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Auto-initialize if not already done
            if _tracer is None:
                init_tracing(endpoint=endpoint)

            tracer = get_tracer()

            with tracer.start_as_current_span(run_name) as span:
                span.set_attribute("span_type", "agent_run")

                # Inject span into function if it accepts trace_span kwarg
                if "trace_span" in func.__code__.co_varnames:
                    kwargs["trace_span"] = span

                result = func(*args, **kwargs)

            # Flush pending spans to the backend before returning
            provider = trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush()

            return result

        return wrapper  # type: ignore

    return decorator


def trace_span(
    name: str | None = None,
    span_type: str = "step",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that traces a function as a nested span.

    Use inside a traced agent run to capture sub-steps, tool calls, and
    LLM calls as child spans:

        @trace_span(name="search_web", span_type="tool_call")
        def search(query: str) -> str:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("span_type", span_type)
                if "trace_span" in func.__code__.co_varnames:
                    kwargs["trace_span"] = span
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def record_input(value: Any) -> None:
    """Record an 'input' event on the current span.

    Mappings are stored as event attributes directly; any other value is
    wrapped as {"value": ...}. No-op when no span is recording.
    """
    _record_event("input", value)


def record_output(value: Any) -> None:
    """Record an 'output' event on the current span. See record_input."""
    _record_event("output", value)


_PRIMITIVES = (str, int, float, bool, bytes, type(None))


def _is_primitive(value: Any) -> bool:
    return isinstance(value, _PRIMITIVES)


def _sanitize_attribute(value: Any) -> Any:
    """Make an event attribute value acceptable to OTel.

    OTel event attributes only accept primitives (str/int/float/bool/bytes/None)
    or sequences of primitives. Anything else — dicts, lists of dicts, tuples —
    is JSON-encoded to a string so nested payloads are preserved instead of
    being silently dropped by the SDK.
    """
    if _is_primitive(value):
        return value
    if isinstance(value, (list, tuple)):
        if all(_is_primitive(v) for v in value):
            return list(value)
        return json.dumps(value, default=str)
    return json.dumps(value, default=str)


def _record_event(event_type: str, value: Any) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    attributes = dict(value) if isinstance(value, Mapping) else {"value": value}
    sanitized = {str(k): _sanitize_attribute(v) for k, v in attributes.items()}
    span.add_event(event_type, sanitized)
