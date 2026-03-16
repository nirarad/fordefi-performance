"""Timing utilities for performance measurement.

Combines Python-side perf_counter with browser-native Performance API
to get both wall-clock and browser-internal timing data.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator, Literal

from playwright.sync_api import Page

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NavigationTiming:
    """Browser-native navigation timing from the Performance API."""
    ttfb_ms: float
    dom_content_loaded_ms: float
    dom_interactive_ms: float
    load_event_end_ms: float


@dataclass
class TimingResult:
    """A single timed measurement combining Python and browser data."""
    action: str
    wall_clock_ms: float
    navigation_timing: NavigationTiming | None = None


@contextmanager
def measure_action(action_name: str) -> Generator[list[float], None, None]:
    """Context manager that records wall-clock duration in milliseconds.

    Usage:
        with measure_action("page_load") as result:
            page.goto(url)
            page.wait_for_selector(selector)
        duration_ms = result[0]
    """
    container: list[float] = []
    start = time.perf_counter()
    yield container
    elapsed_ms = (time.perf_counter() - start) * 1_000
    container.append(elapsed_ms)
    logger.info("%s completed in %.1f ms", action_name, elapsed_ms)


def capture_navigation_timing(page: Page) -> NavigationTiming:
    """Extract PerformanceNavigationTiming from the browser."""
    raw = page.evaluate("""() => {
        const e = performance.getEntriesByType('navigation')[0];
        if (!e) return null;
        return {
            ttfb: e.responseStart - e.requestStart,
            dom_content_loaded: e.domContentLoadedEventEnd,
            dom_interactive: e.domInteractive,
            load_event_end: e.loadEventEnd,
        };
    }""")
    if raw is None:
        logger.warning("PerformanceNavigationTiming not available")
        return NavigationTiming(0, 0, 0, 0)
    return NavigationTiming(
        ttfb_ms=raw["ttfb"],
        dom_content_loaded_ms=raw["dom_content_loaded"],
        dom_interactive_ms=raw["dom_interactive"],
        load_event_end_ms=raw["load_event_end"],
    )


@contextmanager
def measure_network_capture(page: Page) -> Generator[dict[str, Any], None, None]:
    """Context manager that wraps NetworkCapture + nav timing + web vitals.

    Yields a measurement dict that will be populated with:
      - 'network': NetworkCapture
      - 'navigation': NavigationTiming
      - 'vitals': WebVitals
    after the user block completes.
    """
    from core.network_capture import NetworkCapture  # local import to avoid cycles

    measurement: dict[str, Any] = {}
    network = NetworkCapture()
    network.start(page)
    try:
        yield measurement
    finally:
        network.stop()
        nav = capture_navigation_timing(page)
        vitals = capture_web_vitals(page)
        measurement["navigation"] = nav
        measurement["vitals"] = vitals
        measurement["network"] = network


@contextmanager
def measure_page_load(
    page: Page,
    *,
    action_name: str = "page_load",
) -> Generator[dict[str, Any], None, None]:
    """Context manager for full page-load measurements.

    Starts network capture and wall-clock timing, yields a measurement dict
    while the caller performs navigation / waits, then records navigation
    timing and web vitals on exit.
    """
    with measure_network_capture(page) as measurement:
        with measure_action(action_name) as wall_clock:
            measurement["wall_clock"] = wall_clock
            yield measurement


_LCP_OBSERVER_SCRIPT = """() => {
    return new Promise((resolve) => {
        let lcpValue = 0;
        const observer = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            if (entries.length > 0) {
                lcpValue = entries[entries.length - 1].startTime;
            }
        });
        observer.observe({ type: 'largest-contentful-paint', buffered: true });
        // Give the observer a moment to collect buffered entries
        setTimeout(() => {
            observer.disconnect();
            resolve(lcpValue);
        }, 200);
    });
}"""

_CLS_OBSERVER_SCRIPT = """() => {
    return new Promise((resolve) => {
        let clsValue = 0;
        const observer = new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) {
                    clsValue += entry.value;
                }
            }
        });
        observer.observe({ type: 'layout-shift', buffered: true });
        setTimeout(() => {
            observer.disconnect();
            resolve(clsValue);
        }, 200);
    });
}"""


@dataclass
class WebVitals:
    lcp_ms: float
    cls: float


def capture_web_vitals(page: Page) -> WebVitals:
    """Capture LCP and CLS via PerformanceObserver (buffered entries)."""
    try:
        lcp = page.evaluate(_LCP_OBSERVER_SCRIPT)
        cls = page.evaluate(_CLS_OBSERVER_SCRIPT)
    except Exception:
        logger.warning("Web Vitals capture failed, returning zeros")
        return WebVitals(lcp_ms=0, cls=0)
    return WebVitals(lcp_ms=lcp, cls=cls)


def measure_selector_appearance(
    page: Page,
    testid: str,
    *,
    timeout: int = 30_000,
) -> float:
    """Measure time from now until a data-testid selector becomes visible.

    Returns elapsed milliseconds.
    """
    start = time.perf_counter()
    page.locator(f"[data-testid='{testid}']").wait_for(
        state="visible", timeout=timeout,
    )
    elapsed_ms = (time.perf_counter() - start) * 1_000
    logger.info("Selector [data-testid='%s'] visible in %.1f ms", testid, elapsed_ms)
    return elapsed_ms


def wait_for_selector(
    page: Page,
    selector: str,
    *,
    state: Literal["attached", "detached", "hidden", "visible"] = "visible",
    timeout: int = 30_000,
    label: str = "",
) -> float:
    """Wait for a CSS selector to reach the given state and return elapsed ms.

    Args:
        page: Playwright page instance.
        selector: Any valid CSS selector string.
        state: Target state — 'visible', 'hidden', 'attached', 'detached'.
        timeout: Max wait time in milliseconds.
        label: Human-readable label for logging.

    Returns:
        Elapsed milliseconds.
    """
    display_label = label or selector
    start = time.perf_counter()
    page.locator(selector).first.wait_for(state=state, timeout=timeout)
    elapsed_ms = (time.perf_counter() - start) * 1_000
    logger.info("%s reached state '%s' in %.1f ms", display_label, state, elapsed_ms)
    return elapsed_ms
