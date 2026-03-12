"""Compare two performance report JSONs and write benchmark diff + HTML reports.

Usage:
    python scripts/compare_reports.py --baseline path/to/baseline.json --current path/to/current.json [--output-dir dir]

Accepts results.json or detailed_metrics_report.json (list or {"results": [...]}).
Writes to --output-dir (default: reports/<timestamp>_compare):
  - benchmark_diff.json
  - benchmark_diff.csv
  - detailed_benchmark_report.html
  - performance_investigation_report.html (with benchmark section)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.benchmark import compare_results, comparison_to_dict
from core.logger import get_logger
from core.report_writer import (
    load_results_from_json,
    write_benchmark_diff_csv,
    write_benchmark_diff_json,
    write_detailed_benchmark_report,
    write_html_report,
)

logger = get_logger(__name__)

REPORTS_BASE = "reports"


def _load_result_list(path: str) -> list[dict]:
    """Load JSON as list of result dicts (supports results.json or detailed_metrics_report.json)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return [data] if isinstance(data, dict) else []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two performance report JSONs and write benchmark outputs.",
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to baseline results JSON (e.g. reports/<run>/json/results.json)",
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Path to current results JSON to compare against baseline",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for diff and reports (default: reports/<timestamp>_compare)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.baseline):
        logger.error("Baseline file not found: %s", args.baseline)
        return 1
    if not os.path.exists(args.current):
        logger.error("Current file not found: %s", args.current)
        return 1

    if args.output_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        args.output_dir = os.path.join(REPORTS_BASE, f"{ts}_compare")
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "json"), exist_ok=True)

    baseline = _load_result_list(args.baseline)
    current_dicts = _load_result_list(args.current)
    if not baseline:
        logger.error("Baseline file has no results: %s", args.baseline)
        return 1
    if not current_dicts:
        logger.error("Current file has no results: %s", args.current)
        return 1

    comparisons = compare_results(baseline, current_dicts)
    diff_data = comparison_to_dict(comparisons)

    write_benchmark_diff_json(diff_data, run_dir=args.output_dir)
    write_benchmark_diff_csv(diff_data, run_dir=args.output_dir)
    write_detailed_benchmark_report(comparisons, run_dir=args.output_dir)

    current_results = load_results_from_json(args.current)
    write_html_report(
        current_results,
        comparison=comparisons,
        json_path="",
        run_mode="benchmark",
        run_dir=args.output_dir,
        iterations=None,
        warmup=None,
    )

    logger.info("Compare reports written to %s", args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
