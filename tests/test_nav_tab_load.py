"""DDT: Measure page-load performance for every nav-bar tab.

Test data (tab names) is driven by data/scenarios/nav_tabs.csv.
Page-specific details (path, selectors, capabilities) are owned by the
NavBarPage page object.  The test clicks the sidebar nav link, waits for
load indicators, and captures wall-clock time, navigation timing,
web vitals, and console errors.
"""

import pytest
from playwright.sync_api import Page

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
from data.scenario_loader import NavTabScenario, load_nav_tab_scenarios
from pages.nav_bar_page import NavBarPage

logger = get_logger(__name__)

STARTING_PAGE = "/vaults"

nav_tab_scenarios = load_nav_tab_scenarios()


@pytest.mark.performance
@pytest.mark.broad_scan
@pytest.mark.parametrize(
    "scenario",
    nav_tab_scenarios,
    ids=[s.test_id for s in nav_tab_scenarios],
)
def test_nav_tab_load(page: Page, scenario: NavTabScenario) -> None:
    """Navigate to a tab via the sidebar nav bar and measure load performance.

    Steps:
        1. Go to the starting page so the nav bar is rendered.
        2. Look up page details from NavBarPage for the given tab name.
        3. Click the nav-bar link and wait for the URL.
        4. Wait for the spinner to disappear (if supported).
        5. Wait for table rows to appear (if supported).
        6. Capture navigation timing, web vitals, screenshot, and console errors.
    """
    tab_name = scenario.tab_name
    config = NavBarPage.get_tab_config(tab_name)

    console = ConsoleCapture()
    console.start(page)

    page.goto(STARTING_PAGE, wait_until="commit")
    page.wait_for_load_state("domcontentloaded")

    tab_slug = tab_name.lower().replace(" ", "_")

    with measure_action(f"{tab_name} nav-tab load") as wall_clock:
        page.locator(NavBarPage.nav_bar_selector(config.path)).click()
        page.wait_for_url(f"**{config.path}", timeout=30_000)

        if config.supports_spinner and config.spinner_selector:
            spinner_ms = wait_for_selector(
                page,
                config.spinner_selector,
                state="hidden",
                timeout=60_000,
                label=f"{tab_name} spinner",
            )
            logger.info("%s spinner gone in %.0f ms", tab_name, spinner_ms)

        if config.supports_table and config.ready_selector:
            rows_ms = wait_for_selector(
                page,
                config.ready_selector,
                state="visible",
                timeout=60_000,
                label=f"{tab_name} table rows",
            )
            logger.info("%s table rows visible in %.0f ms", tab_name, rows_ms)

    nav = capture_navigation_timing(page)
    vitals = capture_web_vitals(page)
    screenshot_path = take_screenshot(page, tab_slug, "nav_tab_load")
    console.stop()

    result = MeasurementResult.from_page_load(
        tab_name,
        "nav_tab_load",
        wall_clock[0],
        nav,
        vitals,
        console=console,
        screenshot_path=screenshot_path,
    )

    logger.info(
        "%s nav-tab load — wall: %.0f ms | TTFB: %.0f ms | LCP: %.0f ms | errors: %d",
        tab_name,
        result.wall_clock.median,
        result.ttfb.median,
        result.lcp.median,
        result.console_error_count,
    )

    if console.error_count > 0:
        logger.warning(
            "Console errors during %s load: %d", tab_name, console.error_count,
        )
        for entry in console.errors:
            logger.warning("  %s", entry.text[:200])
