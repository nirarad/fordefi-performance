"""Network request tracking for identifying API bottlenecks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import Page, Request, Response

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NetworkEntry:
    method: str
    url: str
    status: int
    duration_ms: float
    size_bytes: int
    timestamp: str


class NetworkCapture:
    """Track network requests and their timing on a Playwright Page."""

    def __init__(self) -> None:
        self._entries: list[NetworkEntry] = []
        self._pending: dict[str, float] = {}
        self._page: Page | None = None

    def start(self, page: Page) -> None:
        self._page = page
        self._entries.clear()
        self._pending.clear()
        page.on("request", self._on_request)
        page.on("response", self._on_response)
        logger.debug("Network capture started")

    def stop(self) -> None:
        if self._page is not None:
            self._page.remove_listener("request", self._on_request)
            self._page.remove_listener("response", self._on_response)
        logger.debug(
            "Network capture stopped — %d entries collected",
            len(self._entries),
        )

    @property
    def entries(self) -> list[NetworkEntry]:
        return list(self._entries)

    def get_slow_requests(self, threshold_ms: float = 1_000) -> list[NetworkEntry]:
        """Return entries with duration above threshold_ms."""
        return [e for e in self._entries if e.duration_ms > threshold_ms]

    def get_summary(self, slow_threshold_ms: float = 1_000) -> dict:
        """Return summary stats for reporting: count, total_ms, slow_count, failed_count."""
        total_ms = sum(e.duration_ms for e in self._entries)
        slow_count = sum(1 for e in self._entries if e.duration_ms > slow_threshold_ms)
        failed_count = sum(1 for e in self._entries if e.status >= 400)
        return {
            "request_count": len(self._entries),
            "total_duration_ms": round(total_ms, 2),
            "slow_count": slow_count,
            "failed_count": failed_count,
        }

    def to_list(self) -> list[dict]:
        return [
            {
                "method": e.method,
                "url": e.url,
                "status": e.status,
                "duration_ms": round(e.duration_ms, 2),
                "size_bytes": e.size_bytes,
                "timestamp": e.timestamp,
            }
            for e in self._entries
        ]

    def _on_request(self, request: Request) -> None:
        import time
        self._pending[request.url] = time.perf_counter()

    def _on_response(self, response: Response) -> None:
        import time
        start = self._pending.pop(response.url, None)
        if start is None:
            return
        duration_ms = (time.perf_counter() - start) * 1_000
        try:
            body = response.body()
            size = len(body)
        except Exception:
            size = 0
        entry = NetworkEntry(
            method=response.request.method,
            url=response.url,
            status=response.status,
            duration_ms=duration_ms,
            size_bytes=size,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._entries.append(entry)
        if duration_ms > 1_000:
            logger.warning(
                "Slow request: %s %s — %.0f ms",
                entry.method, entry.url[:120], duration_ms,
            )
