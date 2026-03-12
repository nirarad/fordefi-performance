"""DDT: Measure load performance for a single item (vault, connected account, or transaction).

From the list table, click the first row and measure time until the detail view
is visible (vault/account widget or transaction sidebar). Scenario data from
data/scenarios/single_item_load.csv.
"""

import pytest
from playwright.sync_api import Page

from configs.tabs import get_single_item_detail_selector
from core.console_capture import ConsoleCapture
from core.evidence import take_screenshot
from core.logger import get_logger
from core.metrics import MeasurementResult
from core.network_capture import NetworkCapture
from core.timing import capture_navigation_timing, capture_web_vitals, measure_action, wait_for_selector
from data.scenario_loader import SingleItemLoadScenario, load_single_item_load_scenarios
from pages.nav_bar_page import NavBarPage
from pages.table_page import TablePage, TransactionTablePage

logger = get_logger(__name__)

STARTING_PAGE = "/vaults"

single_item_scenarios = load_single_item_load_scenarios()


def _run_single_item_load_iteration(
    page: Page,
    tab_name: str,
    nav_page: NavBarPage,
    table_page: TablePage,
    detail_selector: str,
    console: ConsoleCapture,
) -> MeasurementResult:
    """Run one iteration: click first row, wait for detail, capture timings. Caller ensures list is loaded."""
    network = NetworkCapture()
    network.start(page)
    with measure_action(f"{tab_name} single-item load") as wall_clock:
        table_page.click_first_table_row()
        wait_for_selector(
            page,
            detail_selector,
            state="visible",
            timeout=60_000,
            label=f"{tab_name} detail",
        )

    network.stop()
    nav = capture_navigation_timing(page)
    vitals = capture_web_vitals(page)

    return MeasurementResult.from_page_load(
        tab_name,
        "single_item_load",
        wall_clock[0],
        nav,
        vitals,
        console=console,
        network_capture=network,
        screenshot_path="",
    )


@pytest.mark.performance
@pytest.mark.broad_scan
@pytest.mark.parametrize(
    "scenario",
    single_item_scenarios,
    ids=[s.test_id for s in single_item_scenarios],
)
def test_single_item_load(
    page: Page,
    scenario: SingleItemLoadScenario,
    results_collector: list,
    performance_iterations: tuple[int, int],
) -> None:
    """Open list tab, click first table row, measure time until detail view loads.

    Steps:
        1. Go to the starting page so the nav bar is rendered.
        2. Navigate to the tab (Vaults, Connected Accounts, or Transactions).
        3. Wait for table rows to be visible.
        4. Start timing, click the first row, wait for detail (vault widget or transaction sidebar).
        5. Capture navigation timing, web vitals, screenshot, and console errors.

    With --iterations > 1, runs the flow multiple times (discard --warmup runs)
    and aggregates timings (median, P95, std dev).
    """
    total, warmup = performance_iterations
    tab_name = scenario.tab_name
    detail_selector = get_single_item_detail_selector(tab_name)
    if not detail_selector:
        pytest.skip(f"No single-item detail selector configured for {tab_name}")

    nav_page = NavBarPage(page)
    table_page = (
        TransactionTablePage(page)
        if tab_name == "Transactions"
        else TablePage(page)
    )

    console = ConsoleCapture()
    console.start(page)

    page.goto(STARTING_PAGE, wait_until="commit")
    page.wait_for_load_state("domcontentloaded")

    tab_slug = tab_name.lower().replace(" ", "_")
    base_result: MeasurementResult | None = None
    measured_count = 0

    for i in range(total):
        if i > 0:
            page.goto(STARTING_PAGE, wait_until="commit")
            page.wait_for_load_state("domcontentloaded")
        nav_page.navigate_to(tab_name)
        nav_page.wait_for_spinner_gone(tab_name)
        table_page.wait_for_table_rows(tab_name)

        is_warmup = i < warmup
        is_last_measured = (i == total - 1) and not is_warmup

        result = _run_single_item_load_iteration(
            page, tab_name, nav_page, table_page, detail_selector, console,
        )

        if is_warmup:
            continue

        measured_count += 1
        if base_result is None:
            base_result = result
        else:
            base_result.merge_in(result)

        if is_last_measured:
            base_result.screenshot_path = take_screenshot(
                page, tab_slug, "single_item_load",
            )

    if base_result is None:
        return

    base_result.compute_all()
    results_collector.append(base_result)

    logger.info(
        "%s single-item load (n=%d) — wall median: %.0f ms | P95: %.0f ms | TTFB: %.0f ms | LCP: %.0f ms | errors: %d",
        tab_name,
        measured_count,
        base_result.wall_clock.median,
        base_result.wall_clock.p95,
        base_result.ttfb.median,
        base_result.lcp.median,
        base_result.console_error_count,
    )

    console.stop()

    if console.error_count > 0:
        logger.warning(
            "Console errors during %s single-item load: %d",
            tab_name,
            console.error_count,
        )
        for entry in console.errors:
            logger.warning("  %s", entry.text[:200])
