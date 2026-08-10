"""AgentTracer SDK — OpenTelemetry-based tracing for AI agents."""

from .console_exporter import ConsoleSpanExporter
from .exporter import AgentTraceSpanExporter
from .processor import BatchConfig, RetryBatchSpanProcessor
from .setup import (
    get_tracer,
    init_tracing,
    record_input,
    record_output,
    shutdown_tracing,
    trace_agent_run,
    trace_span,
)

__all__ = [
    "AgentTraceSpanExporter",
    "BatchConfig",
    "ConsoleSpanExporter",
    "RetryBatchSpanProcessor",
    "init_tracing",
    "trace_agent_run",
    "trace_span",
    "record_input",
    "record_output",
    "get_tracer",
    "shutdown_tracing",
]
