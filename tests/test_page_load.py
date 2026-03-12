"""Phase 3/4: Simple page-load performance test for the Vaults page.

Vaults is the default page after login. This test measures:
- Wall-clock load time (Python-side perf_counter)
- Browser-native navigation timing (TTFB, DOM load, etc.)
- Core Web Vitals (LCP, CLS)
- Console errors during load
- Screenshot as evidence
"""

import pytest
from playwright.sync_api import Page

from configs.pages import VAULTS_PAGE
from core.console_capture import ConsoleCapture
from core.evidence import take_screenshot
from core.logger import get_logger
from core.metrics import MeasurementResult
from core.timing import (
    capture_navigation_timing,
    capture_web_vitals,
    measure_action,
)

logger = get_logger(__name__)


@pytest.mark.performance
def test_vaults_page_load(page: Page) -> None:
    """Measure initial load performance of the Vaults page."""
    spec = VAULTS_PAGE
    console = ConsoleCapture()
    console.start(page)

    with measure_action(f"{spec.name} page load") as wall_clock:
        page.goto(spec.path, wait_until="networkidle")

    nav = capture_navigation_timing(page)
    vitals = capture_web_vitals(page)

    screenshot_path = take_screenshot(page, spec.name.lower(), "page_load")

    console.stop()

    result = MeasurementResult(
        page_name=spec.name,
        action="page_load",
    )
    result.wall_clock.samples.append(wall_clock[0])
    result.ttfb.samples.append(nav.ttfb_ms)
    result.dom_content_loaded.samples.append(nav.dom_content_loaded_ms)
    result.dom_interactive.samples.append(nav.dom_interactive_ms)
    result.load_event_end.samples.append(nav.load_event_end_ms)
    result.lcp.samples.append(vitals.lcp_ms)
    result.cls.samples.append(vitals.cls)
    result.console_error_count = console.error_count
    result.screenshot_path = screenshot_path
    result.compute_all()

    logger.info(
        "Vaults page load — wall: %.0f ms | TTFB: %.0f ms | LCP: %.0f ms | errors: %d",
        result.wall_clock.median,
        result.ttfb.median,
        result.lcp.median,
        result.console_error_count,
    )

    if console.error_count > 0:
        logger.warning(
            "Console errors during Vaults load: %d",
            console.error_count,
        )
        for entry in console.errors:
            logger.warning("  %s", entry.text[:200])
