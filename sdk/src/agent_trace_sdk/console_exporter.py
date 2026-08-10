from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .exporter import _ns_to_iso


def _span_id(span: ReadableSpan) -> str:
    """Hex-formatted span id, matching the HTTP exporter's convention."""
    if span.context and span.context.span_id:
        return (
            format(span.context.span_id, "x")
            if isinstance(span.context.span_id, int)
            else str(span.context.span_id)
        )
    return "unknown"


def _span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    """Render a span as a plain dict (shared by pretty and json modes)."""
    attrs = dict(span.attributes) if span.attributes else {}
    span_type = attrs.pop("span_type", "step")
    data: dict[str, Any] = {
        "span_id": _span_id(span),
        "name": span.name,
        "span_type": span_type,
        "attributes": attrs,
        "events": [
            {
                "name": e.name,
                "timestamp": _ns_to_iso(e.timestamp) if e.timestamp else "",
                "attributes": dict(e.attributes) if e.attributes else {},
            }
            for e in span.events
        ],
    }
    if span.start_time:
        data["start_time"] = _ns_to_iso(span.start_time)
    if span.end_time:
        data["end_time"] = _ns_to_iso(span.end_time)
        data["duration_ms"] = (span.end_time - span.start_time) / 1_000_000
    return data


class ConsoleSpanExporter(SpanExporter):
    """Print exported spans to stdout instead of sending them over HTTP.
    Mode "pretty" prints human-readable blocks; mode "json" prints one
    JSON object per span. Always returns SUCCESS — printing cannot fail.
    """

    def __init__(self, mode: str = "pretty") -> None:
        if mode not in ("pretty", "json"):
            raise ValueError(f"mode must be 'pretty' or 'json', got {mode!r}")
        self._mode = mode

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if self._mode == "json":
                print(json.dumps(_span_to_dict(span)))
            else:
                self._print_pretty(span)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Nothing to clean up."""

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Printing is synchronous; nothing is buffered."""
        return True

    def _print_pretty(self, span: ReadableSpan) -> None:
        data = _span_to_dict(span)
        lines = [
            f"Span {data['span_id']} [{data['span_type']}]",
            f"  name: {data['name']}",
            f"  start: {data.get('start_time', 'n/a')}",
            f"  end: {data.get('end_time', 'n/a')}",
            f"  duration_ms: {data.get('duration_ms', 'n/a')}",
            f"  attributes: {json.dumps(data['attributes'])}",
        ]
        for event in data["events"]:
            lines.append(
                f"  event: {event['name']} @ {event['timestamp']} {json.dumps(event['attributes'])}"
            )
        print("\n".join(lines))
