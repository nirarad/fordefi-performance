"""Benchmark comparison: current results vs baseline.

Loads a baseline JSON, compares metrics (median) by (page_name, action),
computes delta and percentage change, and applies regression thresholds.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from configs.thresholds import DEFAULT_THRESHOLDS, RegressionThresholds
from core.logger import get_logger

logger = get_logger(__name__)

METRIC_KEYS = [
    "wall_clock",
    "ttfb",
    "dom_content_loaded",
    "dom_interactive",
    "load_event_end",
    "lcp",
    "cls",
]
Status = Literal["improved", "unchanged", "regressed", "new", "missing"]


@dataclass
class MetricComparison:
    """Comparison of one metric (e.g. wall_clock) for one result row."""
    name: str
    baseline_median: float
    current_median: float
    delta: float
    pct_change: float
    status: Status


@dataclass
class RowComparison:
    """Comparison of one (page_name, action) between baseline and current."""
    page_name: str
    action: str
    metrics: list[MetricComparison] = field(default_factory=list)
    console_errors_baseline: int = 0
    console_errors_current: int = 0
    row_status: Status = "unchanged"


def _median_from_result_dict(r: dict, metric_name: str) -> float:
    metrics = r.get("metrics") or {}
    m = metrics.get(metric_name) or {}
    return float(m.get("median_ms", 0) or 0)


def _classify_metric(
    baseline_median: float,
    current_median: float,
    pct_change: float,
    lower_is_better: bool,
    thresholds: RegressionThresholds,
) -> Status:
    """Classify as improved, unchanged, or regressed based on thresholds."""
    if baseline_median == 0 and current_median == 0:
        return "unchanged"
    if baseline_median == 0:
        return "improved" if lower_is_better else "regressed"

    abs_pct = abs(pct_change)
    if abs_pct < 1e-6:
        return "unchanged"

    if lower_is_better:
        # e.g. wall_clock: increase = regressed, decrease = improved
        if pct_change > 0:
            return "regressed" if pct_change >= thresholds.critical_pct else "unchanged"
        return "improved" if abs_pct >= 5 else "unchanged"
    else:
        # e.g. if we had a "score" higher is better
        if pct_change < 0:
            return "regressed" if abs_pct >= thresholds.critical_pct else "unchanged"
        return "improved" if pct_change >= 5 else "unchanged"


def _compare_row(
    baseline_row: dict,
    current_row: dict,
    thresholds: RegressionThresholds,
) -> RowComparison:
    page_name = current_row.get("page_name", baseline_row.get("page_name", ""))
    action = current_row.get("action", baseline_row.get("action", ""))
    metrics: list[MetricComparison] = []
    lower_is_better = True  # for all our metrics (time, LCP, CLS)

    for key in METRIC_KEYS:
        base_med = _median_from_result_dict(baseline_row, key)
        cur_med = _median_from_result_dict(current_row, key)
        delta = cur_med - base_med
        pct = (delta / base_med * 100) if base_med else (100 if cur_med else 0)
        status = _classify_metric(base_med, cur_med, pct, lower_is_better, thresholds)
        metrics.append(MetricComparison(
            name=key,
            baseline_median=base_med,
            current_median=cur_med,
            delta=delta,
            pct_change=pct,
            status=status,
        ))

    row_status = "unchanged"
    if any(m.status == "regressed" for m in metrics):
        row_status = "regressed"
    elif any(m.status == "improved" for m in metrics):
        row_status = "improved"

    return RowComparison(
        page_name=page_name,
        action=action,
        metrics=metrics,
        console_errors_baseline=baseline_row.get("console_error_count", 0),
        console_errors_current=current_row.get("console_error_count", 0),
        row_status=row_status,
    )


def load_baseline(path: str) -> list[dict]:
    """Load baseline results from a JSON file. Returns list of result dicts."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Baseline file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    logger.info("Loaded baseline with %d results from %s", len(data), path)
    return data


def compare_results(
    baseline: list[dict],
    current: list[dict],
    thresholds: RegressionThresholds | None = None,
) -> list[RowComparison]:
    """Compare current results to baseline. Match by (page_name, action)."""
    thresholds = thresholds or DEFAULT_THRESHOLDS
    baseline_by_key = {(r.get("page_name"), r.get("action")): r for r in baseline}
    comparisons: list[RowComparison] = []

    for cur in current:
        key = (cur.get("page_name"), cur.get("action"))
        base = baseline_by_key.get(key)
        if base is None:
            comparisons.append(RowComparison(
                page_name=cur.get("page_name", ""),
                action=cur.get("action", ""),
                row_status="new",
                console_errors_current=cur.get("console_error_count", 0),
            ))
            continue
        comparisons.append(_compare_row(base, cur, thresholds))

    # Rows only in baseline (missing in current)
    current_keys = {(r.get("page_name"), r.get("action")) for r in current}
    for key, base in baseline_by_key.items():
        if key not in current_keys:
            comparisons.append(RowComparison(
                page_name=base.get("page_name", ""),
                action=base.get("action", ""),
                row_status="missing",
                console_errors_baseline=base.get("console_error_count", 0),
            ))

    return comparisons


def comparison_to_dict(comparisons: list[RowComparison]) -> list[dict]:
    """Serialize comparisons for JSON output."""
    out = []
    for c in comparisons:
        out.append({
            "page_name": c.page_name,
            "action": c.action,
            "row_status": c.row_status,
            "console_errors_baseline": c.console_errors_baseline,
            "console_errors_current": c.console_errors_current,
            "metrics": [
                {
                    "name": m.name,
                    "baseline_median_ms": round(m.baseline_median, 2),
                    "current_median_ms": round(m.current_median, 2),
                    "delta_ms": round(m.delta, 2),
                    "pct_change": round(m.pct_change, 2),
                    "status": m.status,
                }
                for m in c.metrics
            ],
        })
    return out
