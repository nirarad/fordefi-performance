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
    """Record wall-clock duration for an arbitrary block of code.

    The context manager yields a single-element list; on exit, the list
    is populated with the elapsed time in milliseconds. Tests then read
    `result[0]` to obtain the measured duration.

    Example:
        with measure_action("page_load") as result:
            page.goto(url)
            page.wait_for_selector(selector)
        duration_ms = result[0]

    Args:
        action_name: Human-readable label used only for logging.

    Yields:
        A mutable list that will contain a single float value
        representing the elapsed milliseconds once the context exits.
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
    """Capture network, navigation timing, and web vitals for a code block.

    This helper is the backbone of the performance tests: it starts a
    `NetworkCapture` before yielding and, once the caller's block
    completes, attaches:

    - ``measurement["network"]``: the `NetworkCapture` instance
    - ``measurement["navigation"]``: a `NavigationTiming` snapshot
    - ``measurement["vitals"]``: a `WebVitals` snapshot

    The caller is expected to also attach a ``"wall_clock"`` entry by
    nesting `measure_action` or `measure_page_load`.

    Args:
        page: Playwright `Page` whose network traffic and performance
            data should be observed.

    Yields:
        A dict that will be populated with network, navigation, and
        vitals information after the inner block finishes.
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
    """Measure a full page load, combining wall-clock, network, and vitals.

    This composes `measure_network_capture` and `measure_action` into a
    single context manager used throughout the tests. On entry it
    starts network capture and wall-clock timing; on exit it provides:

    - ``measurement["wall_clock"]``: list with wall-clock ms
    - ``measurement["network"]``: `NetworkCapture`
    - ``measurement["navigation"]``: `NavigationTiming`
    - ``measurement["vitals"]``: `WebVitals`

    Args:
        page: Playwright `Page` to operate on.
        action_name: Label for logging, e.g. "Login page load".

    Yields:
        A dict into which wall-clock, network, navigation, and vitals
        information will be written by the context manager.
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
    """Wait for a CSS selector to reach a state and return elapsed ms.

    This helper wraps `page.locator(selector).first.wait_for(...)`
    with timing and logging so that tests can measure the latency of
    key UI milestones (for example, table rows becoming visible).

    Args:
        page: Playwright `Page` instance.
        selector: Any valid CSS selector string.
        state: Target locator state — ``"visible"``, ``"hidden"``,
            ``"attached"``, or ``"detached"``.
        timeout: Maximum wait time in milliseconds before raising.
        label: Optional human-readable label used in log messages; if
            omitted, the raw selector is logged.

    Returns:
        The elapsed time in milliseconds between starting the wait and
        the selector reaching the requested state.
    """
    display_label = label or selector
    start = time.perf_counter()
    page.locator(selector).first.wait_for(state=state, timeout=timeout)
    elapsed_ms = (time.perf_counter() - start) * 1_000
    logger.info("%s reached state '%s' in %.1f ms", display_label, state, elapsed_ms)
    return elapsed_ms
