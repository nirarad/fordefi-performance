"""Capture and classify browser console messages during test flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from playwright.sync_api import ConsoleMessage, Page

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConsoleEntry:
    level: str
    text: str
    url: str
    timestamp: str


class ConsoleCapture:
    """Attaches to a Playwright Page and records all console messages."""

    def __init__(self) -> None:
        self._entries: list[ConsoleEntry] = []
        self._page: Page | None = None

    def start(self, page: Page) -> None:
        self._page = page
        self._entries.clear()
        page.on("console", self._on_message)
        logger.debug("Console capture started")

    def stop(self) -> None:
        if self._page is not None:
            self._page.remove_listener("console", self._on_message)
        logger.debug(
            "Console capture stopped — %d entries collected",
            len(self._entries),
        )

    @property
    def entries(self) -> list[ConsoleEntry]:
        return list(self._entries)

    @property
    def errors(self) -> list[ConsoleEntry]:
        return [e for e in self._entries if e.level == "error"]

    @property
    def warnings(self) -> list[ConsoleEntry]:
        return [e for e in self._entries if e.level == "warning"]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def to_list(self) -> list[dict]:
        return [
            {
                "level": e.level,
                "text": e.text,
                "url": e.url,
                "timestamp": e.timestamp,
            }
            for e in self._entries
        ]

    def _on_message(self, msg: ConsoleMessage) -> None:
        entry = ConsoleEntry(
            level=msg.type,
            text=msg.text,
            url=self._page.url if self._page else "",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._entries.append(entry)
        if entry.level == "error":
            logger.warning("Console error captured: %s", entry.text[:200])
