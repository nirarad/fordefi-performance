"""Write measurement results to JSON and CSV artifact files."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

from core.logger import get_logger
from core.metrics import MeasurementResult

logger = get_logger(__name__)

ARTIFACTS_DIR = "artifacts"


def _ts_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(results: list[MeasurementResult], path: str | None = None) -> str:
    """Serialize results to JSON. Returns the file path."""
    out_dir = os.path.join(ARTIFACTS_DIR, "json")
    os.makedirs(out_dir, exist_ok=True)
    if path is None:
        path = os.path.join(out_dir, f"{_ts_prefix()}_results.json")
    data = [r.to_dict() for r in results]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("JSON results written to %s", path)
    return path


def write_csv(results: list[MeasurementResult], path: str | None = None) -> str:
    """Flatten results into a CSV table. Returns the file path."""
    out_dir = os.path.join(ARTIFACTS_DIR, "csv")
    os.makedirs(out_dir, exist_ok=True)
    if path is None:
        path = os.path.join(out_dir, f"{_ts_prefix()}_results.csv")

    fieldnames = [
        "page_name",
        "action",
        "timestamp",
        "wall_clock_median_ms",
        "wall_clock_p95_ms",
        "ttfb_median_ms",
        "dom_content_loaded_median_ms",
        "dom_interactive_median_ms",
        "load_event_end_median_ms",
        "lcp_median_ms",
        "cls_median",
        "console_error_count",
        "screenshot_path",
        "notes",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "page_name": r.page_name,
                "action": r.action,
                "timestamp": r.timestamp,
                "wall_clock_median_ms": round(r.wall_clock.median, 2),
                "wall_clock_p95_ms": round(r.wall_clock.p95, 2),
                "ttfb_median_ms": round(r.ttfb.median, 2),
                "dom_content_loaded_median_ms": round(r.dom_content_loaded.median, 2),
                "dom_interactive_median_ms": round(r.dom_interactive.median, 2),
                "load_event_end_median_ms": round(r.load_event_end.median, 2),
                "lcp_median_ms": round(r.lcp.median, 2),
                "cls_median": round(r.cls.median, 4),
                "console_error_count": r.console_error_count,
                "screenshot_path": r.screenshot_path,
                "notes": r.notes,
            })
    logger.info("CSV results written to %s", path)
    return path


def write_console_errors(entries: list[dict], path: str | None = None) -> str:
    """Write console error entries to a JSON file."""
    out_dir = os.path.join(ARTIFACTS_DIR, "json")
    os.makedirs(out_dir, exist_ok=True)
    if path is None:
        path = os.path.join(out_dir, f"{_ts_prefix()}_console_errors.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    logger.info("Console errors written to %s", path)
    return path
