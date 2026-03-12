"""Phase 3/4: Simple page-load performance test for the Vaults page.

Vaults is the default page after login. This test measures:
- Wall-clock load time (Python-side perf_counter)
- Spinner disappearance time (data fully fetched)
- Table row appearance time (grid rendered with data)
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
    wait_for_selector,
)

logger = get_logger(__name__)


@pytest.mark.performance
def test_vaults_page_load(page: Page) -> None:
    """Measure initial load performance of the Vaults page.

    The page is considered fully loaded when:
    1. The loading spinner disappears (data fetch complete)
    2. At least one MuiDataGrid row is visible (table rendered)
    """
    spec = VAULTS_PAGE
    console = ConsoleCapture()
    console.start(page)

    with measure_action(f"{spec.name} full page load") as wall_clock:
        page.goto(spec.path, wait_until="commit")

        if spec.supports_spinner and spec.spinner_selector:
            spinner_gone_ms = wait_for_selector(
                page,
                spec.spinner_selector,
                state="hidden",
                timeout=60_000,
                label=f"{spec.name} spinner",
            )
            logger.info("%s spinner gone in %.0f ms", spec.name, spinner_gone_ms)

        if spec.supports_table and spec.ready_selector:
            rows_visible_ms = wait_for_selector(
                page,
                spec.ready_selector,
                state="visible",
                timeout=60_000,
                label=f"{spec.name} table rows",
            )
            logger.info("%s table rows visible in %.0f ms", spec.name, rows_visible_ms)

    nav = capture_navigation_timing(page)
    vitals = capture_web_vitals(page)

    screenshot_path = take_screenshot(page, spec.name.lower(), "page_load")

    console.stop()

    result = MeasurementResult.from_page_load(
        spec.name,
        "page_load",
        wall_clock[0],
        nav,
        vitals,
        console=console,
        screenshot_path=screenshot_path,
    )

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
