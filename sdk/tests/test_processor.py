"""Tests for RetryBatchSpanProcessor and ConsoleSpanExporter.

Uses a scriptable fake SpanExporter so failure/retry behavior is tested
deterministically — no HTTP, no sleeps, no threads.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from agent_trace_sdk import (
    BatchConfig,
    ConsoleSpanExporter,
    RetryBatchSpanProcessor,
    init_tracing,
)


class FakeExporter:
    """Records exports and returns a scriptable result."""

    def __init__(
        self,
        result: SpanExportResult = SpanExportResult.SUCCESS,
        results: Sequence[SpanExportResult] | None = None,
    ) -> None:
        self.result = result
        self._results = list(results) if results else None
        self.exported: list[Sequence[ReadableSpan]] = []
        self.shutdown_called = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.exported.append(list(spans))
        if self._results is not None:
            return self._results.pop(0)
        return self.result

    def shutdown(self) -> None:
        self.shutdown_called = True


class FakeSpan:
    """Minimal ReadableSpan stand-in (only fields the processor touches)."""

    def __init__(self, span_id: str = "span-1") -> None:
        self.context = SimpleNamespace(span_id=span_id)


def make_span(span_id: str) -> ReadableSpan:
    return FakeSpan(span_id)  # type: ignore[return-value]


class TestRetryBatchSpanProcessor:
    """Tests for queueing, batching, and failure retention."""

    def test_on_end_queues_span_without_exporting(self) -> None:
        """Below the batch threshold, spans queue but are not exported."""
        exporter = FakeExporter()
        processor = RetryBatchSpanProcessor(exporter)

        processor.on_end(make_span("a"))
        processor.on_end(make_span("b"))

        assert exporter.exported == []

    def test_threshold_triggers_immediate_export(self) -> None:
        """Hitting max_export_batch_size exports a batch right away."""
        exporter = FakeExporter()
        config = BatchConfig(max_export_batch_size=3)
        processor = RetryBatchSpanProcessor(exporter, config)

        processor.on_end(make_span("a"))
        processor.on_end(make_span("b"))
        processor.on_end(make_span("c"))

        assert len(exporter.exported) == 1
        assert [s.context.span_id for s in exporter.exported[0]] == ["a", "b", "c"]

    def test_force_flush_exports_and_clears_on_success(self) -> None:
        """force_flush delivers everything queued and returns True."""
        exporter = FakeExporter()
        processor = RetryBatchSpanProcessor(exporter)
        for i in range(5):
            processor.on_end(make_span(f"s{i}"))

        ok = processor.force_flush()

        assert ok is True
        # 5 spans, default batch size 50 → one batch
        assert len(exporter.exported) == 1
        assert len(exporter.exported[0]) == 5

    def test_failed_export_requeues_spans(self) -> None:
        """On FAILURE the batch is kept for retry and force_flush returns False."""
        exporter = FakeExporter(result=SpanExportResult.FAILURE)
        processor = RetryBatchSpanProcessor(exporter)
        processor.on_end(make_span("a"))
        processor.on_end(make_span("b"))

        ok = processor.force_flush()

        assert ok is False
        assert len(exporter.exported) == 1  # one attempt

        # Retry with a healthy exporter — the same spans must be delivered.
        exporter.result = SpanExportResult.SUCCESS
        ok = processor.force_flush()
        assert ok is True
        assert len(exporter.exported) == 2
        assert [s.context.span_id for s in exporter.exported[1]] == ["a", "b"]

    def test_failed_batch_keeps_queue_position(self) -> None:
        """A failed batch stays at the front; newer spans export after it."""
        exporter = FakeExporter(result=SpanExportResult.FAILURE)
        processor = RetryBatchSpanProcessor(exporter)
        processor.on_end(make_span("old"))
        processor.force_flush()  # fails, "old" requeued

        processor.on_end(make_span("new"))
        exporter.result = SpanExportResult.SUCCESS
        processor.force_flush()

        # Order preserved: old first, then new.
        all_ids = [s.context.span_id for b in exporter.exported[1:] for s in b]
        assert all_ids == ["old", "new"]

    def test_bounded_queue_drops_oldest(self) -> None:
        """At capacity, the oldest spans are dropped (memory guard)."""
        exporter = FakeExporter()
        config = BatchConfig(max_queue_size=3, max_export_batch_size=100)
        processor = RetryBatchSpanProcessor(exporter, config)

        for i in range(5):
            processor.on_end(make_span(f"s{i}"))

        processor.force_flush()
        delivered = [s.context.span_id for b in exporter.exported for s in b]
        assert delivered == ["s2", "s3", "s4"]  # s0, s1 dropped

    def test_flush_splits_large_queue_into_batches(self) -> None:
        """A queue larger than one batch is exported in batch-sized chunks."""
        # 3 threshold exports fail (re-queuing and growing the queue), then
        # force_flush splits the 4-span queue into two 2-span batches.
        exporter = FakeExporter(
            results=[
                SpanExportResult.FAILURE,
                SpanExportResult.FAILURE,
                SpanExportResult.FAILURE,
                SpanExportResult.SUCCESS,
                SpanExportResult.SUCCESS,
            ]
        )
        config = BatchConfig(max_export_batch_size=2)
        processor = RetryBatchSpanProcessor(exporter, config)

        for i in range(4):
            processor.on_end(make_span(f"s{i}"))

        result = processor.force_flush()

        assert result is True
        assert len(exporter.exported) == 5
        delivered = [[s.context.span_id for s in b] for b in exporter.exported]
        assert delivered[-2:] == [["s0", "s1"], ["s2", "s3"]]

    def test_shutdown_flushes_and_closes_exporter(self) -> None:
        """shutdown exports remaining spans and shuts down the exporter."""
        exporter = FakeExporter()
        processor = RetryBatchSpanProcessor(exporter)
        processor.on_end(make_span("a"))

        processor.shutdown()

        assert len(exporter.exported) == 1
        assert exporter.shutdown_called is True

    def test_flush_with_empty_queue_returns_true(self) -> None:
        """force_flush on an empty queue is a no-op success."""
        exporter = FakeExporter()
        processor = RetryBatchSpanProcessor(exporter)
        assert processor.force_flush() is True
        assert exporter.exported == []


class TestConsoleSpanExporter:
    """Tests for pretty/json stdout output."""

    def make_otel_span(self) -> ReadableSpan:
        return SimpleNamespace(
            context=SimpleNamespace(span_id=0xABCDEF),
            name="think",
            attributes={"span_type": "step", "model": "gpt-4"},
            start_time=1704067200000000000,
            end_time=1704067205000000000,
            events=[
                SimpleNamespace(
                    name="input",
                    timestamp=1704067201000000000,
                    attributes={"query": "hello"},
                )
            ],
        )  # type: ignore[return-value]

    def test_pretty_mode_prints_block(self, capsys: pytest.CaptureFixture) -> None:
        exporter = ConsoleSpanExporter(mode="pretty")
        result = exporter.export([self.make_otel_span()])
        out = capsys.readouterr().out

        assert result == SpanExportResult.SUCCESS
        assert "Span abcdef [step]" in out
        assert "name: think" in out
        assert "duration_ms: 5000.0" in out
        assert "model" in out
        assert "event: input" in out

    def test_json_mode_prints_one_json_object(self, capsys: pytest.CaptureFixture) -> None:
        import json

        exporter = ConsoleSpanExporter(mode="json")
        exporter.export([self.make_otel_span()])
        out = capsys.readouterr().out.strip()

        data = json.loads(out)
        assert data["span_id"] == "abcdef"
        assert data["name"] == "think"
        assert data["span_type"] == "step"
        assert data["attributes"] == {"model": "gpt-4"}
        assert data["duration_ms"] == 5000.0
        assert data["events"][0]["name"] == "input"

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode must be"):
            ConsoleSpanExporter(mode="xml")

    def test_force_flush_is_noop_success(self) -> None:
        exporter = ConsoleSpanExporter()
        assert exporter.force_flush() is True

    def test_shutdown_does_not_raise(self) -> None:
        ConsoleSpanExporter().shutdown()


class TestInitTracingInjection:
    """Tests for the exporter injection parameter."""

    def test_init_tracing_accepts_console_exporter(self) -> None:
        """A custom exporter can be injected via init_tracing()."""
        init_tracing(service_name="console-test", exporter=ConsoleSpanExporter(mode="json"))

        from agent_trace_sdk.setup import get_tracer

        assert get_tracer() is not None
