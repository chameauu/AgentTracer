"""Event exporters for the SDK."""
from __future__ import annotations

import json
from typing import Any

from .domain.interfaces import IEventExporter, ExportBatch, ExportError


class HTTPExporter(IEventExporter):
    """Exports events to the AgentTracer backend via HTTP."""

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/ingest/events",
        timeout: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=self._timeout)
            except ImportError:
                raise ImportError("httpx is required for HTTPExporter. Install with: pip install httpx")
        return self._client

    async def export(self, batch: ExportBatch) -> bool:
        client = await self._get_client()
        try:
            response = await client.post(
                self._endpoint,
                json=batch.to_dict(),
                headers={"Content-Type": "application/json", **self._headers},
            )
            response.raise_for_status()
            return True
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_msg = f"HTTP error: {e.response.status_code}"
            raise ExportError(f"Export failed: {error_msg}") from e

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


class ConsoleExporter(IEventExporter):
    """Exports events to stdout for debugging."""

    def __init__(self, output_format: str = "json") -> None:
        self._output_format = output_format

    async def export(self, batch: ExportBatch) -> bool:
        if self._output_format == "json":
            print(json.dumps(batch.to_dict(), indent=2))
        else:
            print(f"Run ID: {batch.run_id}")
            for event in batch.events:
                print(f"  {event.event_type}: {event.span_id} - {event.timestamp}")
        return True

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass