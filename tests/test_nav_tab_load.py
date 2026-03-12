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
from configs.tabs import TabConfig
from data.scenario_loader import NavTabScenario, load_nav_tab_scenarios
from pages.nav_bar_page import NavBarPage
from pages.table_page import TablePage

logger = get_logger(__name__)

STARTING_PAGE = "/vaults"

nav_tab_scenarios = load_nav_tab_scenarios()


def _run_nav_tab_load_iteration(
    page: Page,
    tab_name: str,
    nav_page: NavBarPage,
    table_page: TablePage,
    config: TabConfig,
    tab_slug: str,
    console: ConsoleCapture,
) -> tuple[
    MeasurementResult,
    MeasurementResult | None,
    MeasurementResult | None,
]:
    """Run one iteration of nav-tab load + optional table_render + optional pagination.
    Returns (load_result, table_result or None, pagination_result or None)."""
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

    load_result = MeasurementResult.from_page_load(
        tab_name,
        "nav_tab_load",
        wall_clock[0],
        nav,
        vitals,
        console=console,
        network_capture=network,
        screenshot_path="",
    )

    table_result = None
    if rows_ms is not None:
        table_result = MeasurementResult.from_wall_clock(
            tab_name,
            "table_render",
            rows_ms,
            network_capture=None,
        )

    first_row_id = table_page.first_row_id
    pagination_result = None
    if (
        config.supports_pagination
        and first_row_id is not None
        and table_page.can_paginate_next()
    ):
        network_pg = NetworkCapture()
        network_pg.start(page)
        with measure_action(f"{tab_name} pagination next-page") as pg_clock:
            table_page.click_next_page()
            table_page.wait_for_page_change(tab_name, first_row_id)

        network_pg.stop()

        pagination_result = MeasurementResult.from_wall_clock(
            tab_name,
            "pagination_next",
            pg_clock[0],
            network_capture=network_pg,
            screenshot_path="",
        )
        logger.info("%s pagination next — wall: %.0f ms", tab_name, pg_clock[0])

    return load_result, table_result, pagination_result


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
    performance_iterations: tuple[int, int],
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

    With --iterations > 1, runs the flow multiple times (discard --warmup runs)
    and aggregates timings (median, P95, std dev). Screenshots and network
    evidence are preserved from the last measured run.
    """
    total, warmup = performance_iterations
    tab_name = scenario.tab_name
    nav_page = NavBarPage(page)
    table_page = TablePage(page)
    config = NavBarPage.get_tab_config(tab_name)

    console = ConsoleCapture()
    console.start(page)

    page.goto(STARTING_PAGE, wait_until="commit")
    page.wait_for_load_state("domcontentloaded")

    tab_slug = tab_name.lower().replace(" ", "_")

    base_load: MeasurementResult | None = None
    base_table: MeasurementResult | None = None
    base_pagination: MeasurementResult | None = None
    measured_count = 0

    for i in range(total):
        if i > 0:
            page.goto(STARTING_PAGE, wait_until="commit")
            page.wait_for_load_state("domcontentloaded")

        is_warmup = i < warmup
        is_last_measured = (i == total - 1) and not is_warmup

        load_result, table_result, pagination_result = _run_nav_tab_load_iteration(
            page, tab_name, nav_page, table_page, config, tab_slug, console,
        )

        if is_warmup:
            continue

        measured_count += 1

        if base_load is None:
            base_load = load_result
            base_table = table_result
            base_pagination = pagination_result
        else:
            base_load.merge_in(load_result)
            if base_table is not None and table_result is not None:
                base_table.merge_in(table_result)
            if base_pagination is not None and pagination_result is not None:
                base_pagination.merge_in(pagination_result)

        if is_last_measured:
            base_load.screenshot_path = take_screenshot(page, tab_slug, "nav_tab_load")
            if base_table is not None:
                base_table.screenshot_path = base_load.screenshot_path
            if base_pagination is not None:
                base_pagination.screenshot_path = take_screenshot(
                    page, tab_slug, "pagination_next",
                )

    if base_load is None:
        return

    base_load.compute_all()
    results_collector.append(base_load)
    if base_table is not None:
        base_table.compute_all()
        results_collector.append(base_table)
    if base_pagination is not None:
        base_pagination.compute_all()
        results_collector.append(base_pagination)

    logger.info(
        "%s nav-tab load (n=%d) — wall median: %.0f ms | P95: %.0f ms | TTFB: %.0f ms | LCP: %.0f ms | errors: %d",
        tab_name,
        measured_count,
        base_load.wall_clock.median,
        base_load.wall_clock.p95,
        base_load.ttfb.median,
        base_load.lcp.median,
        base_load.console_error_count,
    )

    if config.supports_pagination and base_pagination is None:
        logger.warning("%s: next-page button not available — skipping pagination", tab_name)

    console.stop()

    if console.error_count > 0:
        logger.warning(
            "Console errors during %s: %d", tab_name, console.error_count,
        )
        for entry in console.errors:
            logger.warning("  %s", entry.text[:200])
