"""Evidence collection: screenshots, traces, and artifact management."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from playwright.sync_api import BrowserContext, Page

from core.logger import get_logger

logger = get_logger(__name__)

REPORTS_BASE = "reports"

# When set (e.g. by conftest for performance runs), all outputs go under this directory.
_run_dir: str | None = None


def set_run_dir(path: str) -> None:
    """Set the run directory for this session (one folder per run with all assets)."""
    global _run_dir
    _run_dir = path


def get_run_dir() -> str:
    """Return the current run directory. Lazy-creates reports/<timestamp> if not set."""
    global _run_dir
    if _run_dir is not None:
        return _run_dir
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _run_dir = os.path.join(REPORTS_BASE, ts)
    os.makedirs(_run_dir, exist_ok=True)
    return _run_dir


def _ts_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def take_screenshot(
    page: Page,
    page_name: str,
    action: str,
) -> str:
    """Save a full-page screenshot and return the file path."""
    base = get_run_dir()
    out_dir = os.path.join(base, "screenshots")
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
    base = get_run_dir()
    out_dir = os.path.join(base, "traces")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{_ts_prefix()}_{page_name}_{action}.zip"
    filepath = os.path.join(out_dir, filename)
    context.tracing.stop(path=filepath)
    logger.info("Trace saved: %s", filepath)
    return filepath
