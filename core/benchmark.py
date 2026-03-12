"""Benchmark comparator: compare current results against a baseline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum

from configs.thresholds import DEFAULT_THRESHOLDS, RegressionThresholds
from core.logger import get_logger

logger = get_logger(__name__)


class Status(Enum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    REGRESSED_WARNING = "regressed_warning"
    REGRESSED_CRITICAL = "regressed_critical"


@dataclass
class MetricDelta:
    metric_name: str
    baseline_ms: float
    current_ms: float
    absolute_delta_ms: float
    percentage_delta: float
    status: Status


@dataclass
class BenchmarkComparison:
    page_name: str
    action: str
    deltas: list[MetricDelta]

    @property
    def has_regression(self) -> bool:
        return any(
            d.status in (Status.REGRESSED_WARNING, Status.REGRESSED_CRITICAL)
            for d in self.deltas
        )


def _classify(pct_delta: float, thresholds: RegressionThresholds) -> Status:
    if pct_delta <= -thresholds.warning_pct:
        return Status.IMPROVED
    if pct_delta >= thresholds.critical_pct:
        return Status.REGRESSED_CRITICAL
    if pct_delta >= thresholds.warning_pct:
        return Status.REGRESSED_WARNING
    return Status.UNCHANGED


def load_baseline(path: str) -> list[dict]:
    """Load a previously saved JSON results file."""
    if not os.path.exists(path):
        logger.error("Baseline file not found: %s", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare(
    baseline: list[dict],
    current: list[dict],
    thresholds: RegressionThresholds = DEFAULT_THRESHOLDS,
) -> list[BenchmarkComparison]:
    """Compare current results against baseline, metric by metric."""
    baseline_map: dict[str, dict] = {}
    for entry in baseline:
        key = f"{entry['page_name']}|{entry['action']}"
        baseline_map[key] = entry

    comparisons: list[BenchmarkComparison] = []

    for entry in current:
        key = f"{entry['page_name']}|{entry['action']}"
        base_entry = baseline_map.get(key)
        if base_entry is None:
            logger.info("No baseline found for %s — skipping comparison", key)
            continue

        deltas: list[MetricDelta] = []
        for metric_name in entry.get("metrics", {}):
            cur_val = entry["metrics"][metric_name].get("median_ms", 0)
            base_val = base_entry.get("metrics", {}).get(metric_name, {}).get("median_ms", 0)
            if base_val == 0:
                continue
            abs_delta = cur_val - base_val
            pct_delta = (abs_delta / base_val) * 100
            status = _classify(pct_delta, thresholds)
            deltas.append(MetricDelta(
                metric_name=metric_name,
                baseline_ms=base_val,
                current_ms=cur_val,
                absolute_delta_ms=round(abs_delta, 2),
                percentage_delta=round(pct_delta, 2),
                status=status,
            ))
            if status in (Status.REGRESSED_WARNING, Status.REGRESSED_CRITICAL):
                logger.warning(
                    "REGRESSION %s | %s | %s: %.0f ms -> %.0f ms (%+.1f%%)",
                    key, metric_name, status.value,
                    base_val, cur_val, pct_delta,
                )

        comparisons.append(BenchmarkComparison(
            page_name=entry["page_name"],
            action=entry["action"],
            deltas=deltas,
        ))

    return comparisons


def comparisons_to_list(comparisons: list[BenchmarkComparison]) -> list[dict]:
    """Serialize comparisons to a JSON-friendly list."""
    out = []
    for c in comparisons:
        for d in c.deltas:
            out.append({
                "page_name": c.page_name,
                "action": c.action,
                "metric": d.metric_name,
                "baseline_ms": d.baseline_ms,
                "current_ms": d.current_ms,
                "absolute_delta_ms": d.absolute_delta_ms,
                "percentage_delta": d.percentage_delta,
                "status": d.status.value,
            })
    return out
