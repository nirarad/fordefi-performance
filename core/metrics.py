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
            "screenshot_path": self.screenshot_path,
            "trace_path": self.trace_path,
            "har_path": self.har_path,
            "notes": self.notes,
            "network_summary": self.network_summary,
            "network_calls": self.network_calls,
        }
