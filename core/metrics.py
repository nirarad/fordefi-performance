"""Statistical aggregation for multi-iteration performance measurements."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from core.network_capture import NetworkCapture

if TYPE_CHECKING:
    from core.console_capture import ConsoleCapture
    from core.timing import NavigationTiming, WebVitals


@dataclass
class AggregatedMetric:
    name: str
    samples: list[float] = field(default_factory=list)
    median: float = 0
    p95: float = 0
    p99: float = 0
    std_dev: float = 0
    min_val: float = 0
    max_val: float = 0

    def compute(self) -> None:
        """Recompute statistics from current samples."""
        if not self.samples:
            return
        sorted_s = sorted(self.samples)
        n = len(sorted_s)
        self.median = statistics.median(sorted_s)
        self.p95 = sorted_s[min(math.ceil(n * 0.95) - 1, n - 1)]
        self.p99 = sorted_s[min(math.ceil(n * 0.99) - 1, n - 1)]
        self.std_dev = statistics.stdev(sorted_s) if n >= 2 else 0
        self.min_val = sorted_s[0]
        self.max_val = sorted_s[-1]

    def outlier_indices(self, factor: float = 2.0) -> list[int]:
        """Return indices of samples deviating > factor * std_dev from median."""
        if self.std_dev == 0:
            return []
        threshold = factor * self.std_dev
        return [
            i for i, s in enumerate(self.samples)
            if abs(s - self.median) > threshold
        ]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sample_count": len(self.samples),
            "median_ms": round(self.median, 2),
            "p95_ms": round(self.p95, 2),
            "p99_ms": round(self.p99, 2),
            "std_dev_ms": round(self.std_dev, 2),
            "min_ms": round(self.min_val, 2),
            "max_ms": round(self.max_val, 2),
        }

    @classmethod
    def from_dict(cls, d: dict) -> AggregatedMetric:
        """Build from serialized dict (e.g. to_dict output). Preserves stats; samples set to median repeated for sample_count."""
        name = d.get("name", "")
        metric = cls(name=name)
        sample_count = int(d.get("sample_count", 0) or 0)
        median_ms = float(d.get("median_ms", 0) or 0)
        metric.median = median_ms
        metric.p95 = float(d.get("p95_ms", 0) or 0)
        metric.p99 = float(d.get("p99_ms", 0) or 0)
        metric.std_dev = float(d.get("std_dev_ms", 0) or 0)
        metric.min_val = float(d.get("min_ms", 0) or 0)
        metric.max_val = float(d.get("max_ms", 0) or 0)
        if sample_count > 0:
            metric.samples = [median_ms] * sample_count
        return metric


@dataclass
class MeasurementResult:
    """Complete measurement result for a single page + action combination."""
    page_name: str
    action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    wall_clock: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("wall_clock"))
    ttfb: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("ttfb"))
    dom_content_loaded: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("dom_content_loaded"))
    dom_interactive: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("dom_interactive"))
    load_event_end: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("load_event_end"))
    lcp: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("lcp"))
    cls: AggregatedMetric = field(default_factory=lambda: AggregatedMetric("cls"))
    console_error_count: int = 0
    console_example_error: str = ""
    screenshot_path: str = ""
    trace_path: str = ""
    har_path: str = ""
    notes: str = ""
    network_calls: list[dict] = field(default_factory=list)
    network_summary: dict = field(default_factory=dict)

    def compute_all(self) -> None:
        """Recompute statistics on every aggregated metric."""
        for m in self._all_metrics():
            m.compute()

    def merge_in(self, other: MeasurementResult) -> None:
        """Append samples from another result (same page/action) and take evidence from other.
        Call compute_all() after all merges to update median, p95, std_dev, etc."""
        self_metrics = self._all_metrics()
        other_metrics = other._all_metrics()
        for sm, om in zip(self_metrics, other_metrics):
            sm.samples.extend(om.samples)
        self.console_error_count = max(self.console_error_count, other.console_error_count)
        self.console_example_error = self.console_example_error or other.console_example_error
        self.screenshot_path = other.screenshot_path or self.screenshot_path
        self.trace_path = other.trace_path or self.trace_path
        self.har_path = other.har_path or self.har_path
        self.notes = other.notes or self.notes
        self.network_calls = other.network_calls or self.network_calls
        self.network_summary = other.network_summary or self.network_summary

    def _all_metrics(self) -> list[AggregatedMetric]:
        return [
            self.wall_clock,
            self.ttfb,
            self.dom_content_loaded,
            self.dom_interactive,
            self.load_event_end,
            self.lcp,
            self.cls,
        ]

    @classmethod
    def from_page_load(
        cls,
        page_name: str,
        action: str,
        wall_clock_ms: float,
        nav: NavigationTiming,
        vitals: WebVitals,
        *,
        console: ConsoleCapture | None = None,
        network_capture: NetworkCapture | None = None,
        screenshot_path: str = "",
    ) -> MeasurementResult:
        """Build a result populated with navigation timing, vitals, console, and network data."""
        result = cls(page_name=page_name, action=action)
        result.wall_clock.samples.append(wall_clock_ms)
        result.ttfb.samples.append(nav.ttfb_ms)
        result.dom_content_loaded.samples.append(nav.dom_content_loaded_ms)
        result.dom_interactive.samples.append(nav.dom_interactive_ms)
        result.load_event_end.samples.append(nav.load_event_end_ms)
        result.lcp.samples.append(vitals.lcp_ms)
        result.cls.samples.append(vitals.cls)
        if console is not None:
            result.console_error_count = console.error_count
            if console.errors:
                result.console_example_error = (console.errors[0].text or "")[:500]
        if network_capture is not None:
            result.network_calls = network_capture.to_list()
            result.network_summary = network_capture.get_summary()
        result.screenshot_path = screenshot_path
        result.compute_all()
        return result

    @classmethod
    def from_wall_clock(
        cls,
        page_name: str,
        action: str,
        wall_clock_ms: float,
        *,
        network_capture: NetworkCapture | None = None,
        screenshot_path: str = "",
    ) -> MeasurementResult:
        """Build a minimal result with only a wall-clock sample (and optional network)."""
        result = cls(page_name=page_name, action=action)
        result.wall_clock.samples.append(wall_clock_ms)
        if network_capture is not None:
            result.network_calls = network_capture.to_list()
            result.network_summary = network_capture.get_summary()
        result.screenshot_path = screenshot_path
        result.compute_all()
        return result

    def to_dict(self) -> dict:
        return {
            "page_name": self.page_name,
            "action": self.action,
            "timestamp": self.timestamp,
            "metrics": {m.name: m.to_dict() for m in self._all_metrics()},
            "console_error_count": self.console_error_count,
            "console_example_error": self.console_example_error,
            "screenshot_path": self.screenshot_path,
            "trace_path": self.trace_path,
            "har_path": self.har_path,
            "notes": self.notes,
            "network_summary": self.network_summary,
            "network_calls": self.network_calls,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MeasurementResult:
        """Build from serialized dict (e.g. results.json or to_dict output)."""
        result = cls(
            page_name=d.get("page_name", ""),
            action=d.get("action", ""),
            timestamp=d.get("timestamp", ""),
            console_error_count=int(d.get("console_error_count", 0) or 0),
            console_example_error=d.get("console_example_error", "") or "",
            screenshot_path=d.get("screenshot_path", "") or "",
            trace_path=d.get("trace_path", "") or "",
            har_path=d.get("har_path", "") or "",
            notes=d.get("notes", "") or "",
            network_summary=d.get("network_summary") or {},
            network_calls=d.get("network_calls") or [],
        )
        metrics_data = d.get("metrics") or {}
        all_metrics = result._all_metrics()
        for m in all_metrics:
            if m.name in metrics_data:
                sub = metrics_data[m.name]
                if isinstance(sub, dict):
                    restored = AggregatedMetric.from_dict(sub)
                    m.samples[:] = restored.samples
                    m.median = restored.median
                    m.p95 = restored.p95
                    m.p99 = restored.p99
                    m.std_dev = restored.std_dev
                    m.min_val = restored.min_val
                    m.max_val = restored.max_val
        return result
