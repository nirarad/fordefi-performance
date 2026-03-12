"""DDT: Measure page-load performance for every nav-bar tab.

Test data (tab names) is driven by data/scenarios/nav_tabs.csv.
Page-specific details (path, selectors, capabilities) are owned by the
NavBarPage page object.  The test clicks the sidebar nav link, waits for
load indicators, and captures wall-clock time, navigation timing,
web vitals, and console errors.

After the initial load, tabs that support pagination get a second
measurement: click next-page and time the table reload.
"""

import pytest
from playwright.sync_api import Page

from core.console_capture import ConsoleCapture
from core.evidence import take_screenshot
from core.logger import get_logger
from core.metrics import MeasurementResult
from core.network_capture import NetworkCapture
from core.timing import capture_navigation_timing, capture_web_vitals, measure_action
from data.scenario_loader import NavTabScenario, load_nav_tab_scenarios
from pages.nav_bar_page import NavBarPage
from pages.table_page import TablePage

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
def test_nav_tab_load(
    page: Page,
    scenario: NavTabScenario,
    results_collector: list,
) -> None:
    """Navigate to a tab via the sidebar nav bar and measure load performance.

    Steps:
        1. Go to the starting page so the nav bar is rendered.
        2. Click the nav-bar link and wait for the URL.
        3. Wait for the spinner to disappear (if supported).
        4. Wait for table rows to appear (if supported).
        5. Capture navigation timing, web vitals, screenshot, and console errors.
        6. If the tab supports pagination and the next-page button is enabled,
           click it and measure the time until the new rows are rendered.
    """
    tab_name = scenario.tab_name
    nav_page = NavBarPage(page)
    table_page = TablePage(page)
    config = NavBarPage.get_tab_config(tab_name)

    console = ConsoleCapture()
    console.start(page)

    page.goto(STARTING_PAGE, wait_until="commit")
    page.wait_for_load_state("domcontentloaded")

    tab_slug = tab_name.lower().replace(" ", "_")

    # -- Phase 1: initial tab load -------------------------------------------

    network = NetworkCapture()
    network.start(page)
    with measure_action(f"{tab_name} nav-tab load") as wall_clock:
        nav_page.navigate_to(tab_name)

        spinner_ms = nav_page.wait_for_spinner_gone(tab_name)
        if spinner_ms is not None:
            logger.info("%s spinner gone in %.0f ms", tab_name, spinner_ms)

        rows_ms = table_page.wait_for_table_rows(tab_name)
        if rows_ms is not None:
            logger.info("%s table rows visible in %.0f ms", tab_name, rows_ms)

    network.stop()
    nav = capture_navigation_timing(page)
    vitals = capture_web_vitals(page)
    screenshot_path = take_screenshot(page, tab_slug, "nav_tab_load")

    load_result = MeasurementResult.from_page_load(
        tab_name,
        "nav_tab_load",
        wall_clock[0],
        nav,
        vitals,
        console=console,
        network_capture=network,
        screenshot_path=screenshot_path,
    )
    results_collector.append(load_result)

    logger.info(
        "%s nav-tab load — wall: %.0f ms | TTFB: %.0f ms | LCP: %.0f ms | errors: %d",
        tab_name,
        load_result.wall_clock.median,
        load_result.ttfb.median,
        load_result.lcp.median,
        load_result.console_error_count,
    )

    # -- Phase 2: pagination (next page) -------------------------------------

    first_row_id = table_page.first_row_id

    if (
        config.supports_pagination
        and first_row_id is not None
        and table_page.can_paginate_next()
    ):
        with measure_action(f"{tab_name} pagination next-page") as pg_clock:
            table_page.click_next_page()
            table_page.wait_for_page_change(tab_name, first_row_id)

        take_screenshot(page, tab_slug, "pagination_next")
        logger.info("%s pagination next — wall: %.0f ms", tab_name, pg_clock[0])
    elif config.supports_pagination:
        logger.warning("%s: next-page button not available — skipping pagination", tab_name)

    console.stop()

    if console.error_count > 0:
        logger.warning(
            "Console errors during %s: %d", tab_name, console.error_count,
        )
        for entry in console.errors:
            logger.warning("  %s", entry.text[:200])
