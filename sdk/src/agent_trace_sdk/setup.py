"""Setup and initialization for OpenTelemetry-based AgentTracer SDK."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .exporter import AgentTraceSpanExporter

P = ParamSpec("P")
R = TypeVar("R")

_tracer: trace.Tracer | None = None


_DEFAULT_ENDPOINT = "http://localhost:8000/api/v1/ingest/events"


def init_tracing(
    service_name: str = "agent-tracer",
    endpoint: str | None = None,
) -> None:
    """Initialize OpenTelemetry tracing with the AgentTrace exporter.

    Call this once at application startup to set up the global tracer provider.

    Args:
        service_name: Name of your service/agent (used as resource attribute).
        endpoint: URL of the AgentTrace backend ingest endpoint.
            Defaults to http://localhost:8000/api/v1/ingest/events.
    """
    global _tracer

    if endpoint is None:
        endpoint = _DEFAULT_ENDPOINT

    provider = TracerProvider()
    exporter = AgentTraceSpanExporter(endpoint=endpoint)
    processor = BatchSpanProcessor(exporter)
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
