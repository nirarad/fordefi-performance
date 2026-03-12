"""Evidence collection: screenshots, traces, and artifact management."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from playwright.sync_api import BrowserContext, Page

from core.logger import get_logger

logger = get_logger(__name__)

ARTIFACTS_DIR = "artifacts"


def _ts_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def take_screenshot(
    page: Page,
    page_name: str,
    action: str,
) -> str:
    """Save a full-page screenshot and return the file path."""
    out_dir = os.path.join(ARTIFACTS_DIR, "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{_ts_prefix()}_{page_name}_{action}.png"
    filepath = os.path.join(out_dir, filename)
    page.screenshot(path=filepath, full_page=True)
    logger.info("Screenshot saved: %s", filepath)
    return filepath


def start_tracing(context: BrowserContext, name: str) -> None:
    """Begin a Playwright trace on the given context."""
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    logger.info("Tracing started for: %s", name)


def stop_tracing(context: BrowserContext, page_name: str, action: str) -> str:
    """Stop tracing and save the trace zip. Returns the file path."""
    out_dir = os.path.join(ARTIFACTS_DIR, "traces")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{_ts_prefix()}_{page_name}_{action}.zip"
    filepath = os.path.join(out_dir, filename)
    context.tracing.stop(path=filepath)
    logger.info("Trace saved: %s", filepath)
    return filepath
