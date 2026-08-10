"""Retry-aware batch span processor for the AgentTracer SDK.
Substitutes OTel's stock BatchSpanProcessor: unlike the stock one, spans
whose export returns FAILURE are kept in the queue and retried on the next
flush instead of being silently dropped.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
    SpanProcessor,
)


@dataclass(frozen=True)
class BatchConfig:
    """Tuning knobs for RetryBatchSpanProcessor."""

    max_queue_size: int = 100
    max_export_batch_size: int = 50


class RetryBatchSpanProcessor(SpanProcessor):
    """Queue spans, export in batches, and keep them on failure.
    Contract:
    - ``on_end`` enqueues a span; once the queue reaches
      ``max_export_batch_size`` a batch is exported immediately.
    - A failed export re-queues the batch at the front, so it is retried
      on the next flush. Nothing is lost unless the bounded queue overflows.
    - ``force_flush`` exports everything currently queued.
    """

    def __init__(
        self,
        exporter: SpanExporter,
        config: BatchConfig | None = None,
    ) -> None:
        self._exporter = exporter
        self._config = config or BatchConfig()
        self._queue: deque[ReadableSpan] = deque(maxlen=self._config.max_queue_size)
        self._lock = Lock()

    def on_start(self, span: ReadableSpan, parent_context=None) -> None:
        """No-op; nothing to do when a span starts."""

    def on_end(self, span: ReadableSpan) -> None:
        """Enqueue a finished span, exporting when the batch threshold is hit."""
        with self._lock:
            self._queue.append(span)
            should_export = len(self._queue) >= self._config.max_export_batch_size
        if should_export:
            self._export_batch()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Export all queued spans. Returns True when every batch succeeded."""
        return self._export_all()

    def shutdown(self) -> None:
        """Flush remaining spans and shut down the exporter."""
        self._export_all()
        self._exporter.shutdown()

    def _take_batch(self) -> list[ReadableSpan]:
        """Remove and return up to max_export_batch_size spans."""
        with self._lock:
            size = min(self._config.max_export_batch_size, len(self._queue))
            return [self._queue.popleft() for _ in range(size)]

    def _requeue(self, batch: list[ReadableSpan]) -> None:
        """Put a failed batch back at the front, oldest first."""
        with self._lock:
            self._queue.extendleft(reversed(batch))

    def _export_batch(self) -> bool:
        """Export a single batch; re-queue it on failure."""
        batch = self._take_batch()
        if not batch:
            return True
        if self._exporter.export(batch) is not SpanExportResult.SUCCESS:
            self._requeue(batch)
            return False
        return True

    def _export_all(self) -> bool:
        """Keep exporting batches until the queue is empty or an export fails."""
        ok = True
        while self._queue:
            if not self._export_batch():
                ok = False
                break
        return ok
