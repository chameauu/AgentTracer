"""OpenTelemetry SpanExporter that sends traces to AgentTracer backend."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class AgentTraceSpanExporter(SpanExporter):
    """Exports OTel spans to the AgentTracer backend.

    Converts OpenTelemetry spans into the format expected by
    POST /api/v1/ingest/events and sends them in batches.
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/ingest/events",
        timeout: float = 5.0,
    ) -> None:
        self._endpoint = endpoint
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export a batch of OTel spans to the backend."""
        import asyncio

        try:
            # Check if we're already in an async context
            try:
                asyncio.get_running_loop()
                # We're in an async context - we can't use asyncio.run()
                # Instead, create a new thread to run the async code
                import threading

                def run_in_thread():
                    asyncio.run(self._export_async(spans))

                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join(timeout=30)  # Wait max 30 seconds
                return SpanExportResult.SUCCESS
            except RuntimeError:
                # No running event loop - use asyncio.run()
                asyncio.run(self._export_async(spans))
                return SpanExportResult.SUCCESS
        except Exception as e:
            print(f"AgentTrace export failed: {e}")
            return SpanExportResult.FAILURE

    async def _export_async(self, spans: Sequence[ReadableSpan]) -> None:
        if not spans:
            return

        client = await self._get_client()
        events: list[dict[str, Any]] = []
        run_id: str | None = None
        run_name: str | None = None

        for span in spans:
            # Handle both int and string span_id
            if span.context and span.context.span_id:
                span_id = (
                    format(span.context.span_id, "x")
                    if isinstance(span.context.span_id, int)
                    else str(span.context.span_id)
                )
            else:
                span_id = "unknown"
            if run_id is None:
                run_id = span_id

            # Convert OTel span attributes
            attrs = dict(span.attributes) if span.attributes else {}
            span_name = span.name
            span_type = attrs.pop("span_type", "step")

            # The agent_run span names the run (backend falls back to run-{id[:8]})
            if span_type == "agent_run" and run_name is None:
                run_name = span_name

            # span_start event
            start_time_ns = span.start_time
            start_time_iso = _ns_to_iso(start_time_ns) if start_time_ns else ""

            parent_id = None
            if span.parent and span.parent.span_id:
                parent_id = (
                    format(span.parent.span_id, "x")
                    if isinstance(span.parent.span_id, int)
                    else str(span.parent.span_id)
                )

            events.append(
                {
                    "type": "span_start",
                    "data": {
                        "span_id": span_id,
                        "parent_id": parent_id,
                        "name": span_name,
                        "span_type": span_type,
                        "timestamp": start_time_iso,
                        "attributes": attrs,
                    },
                }
            )

            # span_end event
            end_time_ns = span.end_time
            if end_time_ns:
                end_time_iso = _ns_to_iso(end_time_ns)
                events.append(
                    {
                        "type": "span_end",
                        "data": {
                            "span_id": span_id,
                            "timestamp": end_time_iso,
                            "attributes": {},
                        },
                    }
                )

            # Convert OTel events to span_event format
            for otel_event in span.events:
                event_time_iso = _ns_to_iso(otel_event.timestamp) if otel_event.timestamp else ""
                events.append(
                    {
                        "type": "span_event",
                        "data": {
                            "span_id": span_id,
                            "event_type": otel_event.name,
                            "timestamp": event_time_iso,
                            "payload": dict(otel_event.attributes) if otel_event.attributes else {},
                        },
                    }
                )

        if not events:
            return

        payload = {
            "run_id": run_id or "unknown",
            "events": events,
        }
        if run_name is not None:
            payload["run_name"] = run_name

        response = await client.post(self._endpoint, json=payload)
        response.raise_for_status()

    def shutdown(self) -> None:
        """Clean up the exporter."""
        import asyncio

        if self._client:
            try:
                asyncio.run(self._client.aclose())
            except Exception:
                pass
            self._client = None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush is a no-op since we send immediately."""
        return True


def _ns_to_iso(ns: int) -> str:
    """Convert nanoseconds since epoch to ISO 8601 string."""
    from datetime import datetime, timezone

    sec = ns / 1_000_000_000
    return datetime.fromtimestamp(sec, tz=timezone.utc).isoformat()
