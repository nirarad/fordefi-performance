"""Login performance benchmarks.

Measures two distinct phases:
1. Login page load — time from navigation to BASE_URL until the Auth0 login
   form is rendered (email input visible).
2. Login flow — time from filling credentials through the two-step Auth0
   flow until the post-login redirect completes (app URL reached).

Both tests use an unauthenticated browser context so they exercise the
real login path regardless of any saved session state.
"""

import os

import pytest
from playwright.sync_api import Page

from core.console_capture import ConsoleCapture
from core.evidence import take_screenshot
from core.logger import get_logger
from core.metrics import MeasurementResult
from core.network_capture import NetworkCapture
from core.timing import (
    measure_action,
    measure_page_load,
)
from pages.login_page import LoginPage

logger = get_logger(__name__)

BASE_URL = os.getenv("BASE_URL", "https://app.preprod.fordefi.com")


def _require_credentials() -> tuple[str, str]:
    username = os.getenv("FORDEFI_USERNAME")
    password = os.getenv("FORDEFI_PASSWORD")
    if not username or not password:
        pytest.fail(
            "FORDEFI_USERNAME and FORDEFI_PASSWORD must be set in .env "
            "to run login performance tests."
        )
    return username, password


@pytest.mark.performance
def test_login_page_load(
    unauthenticated_page: Page,
    results_collector: list,
    performance_iterations: tuple[int, int],
) -> None:
    """Measure time to load and render the Auth0 login page.

    Clock starts at navigation and stops when the email input is visible.
    With --iterations > 1, runs the load multiple times and aggregates timings.
    """
    page = unauthenticated_page
    login_page = LoginPage(page)
    total, warmup = performance_iterations

    console = ConsoleCapture()
    console.start(page)

    base_result: MeasurementResult | None = None
    measured_count = 0

    for i in range(total):
        with measure_page_load(page, action_name="Login page load") as measurement:
            page.goto(BASE_URL, wait_until="commit")
            login_page.wait_for_login_form()

        result = MeasurementResult.from_page_load(
            "Login",
            "page_load",
            measurement["wall_clock"][0],
            measurement["navigation"],
            measurement["vitals"],
            console=console,
            network_capture=measurement["network"],
            screenshot_path="",
        )

        if i >= warmup:
            measured_count += 1
            if base_result is None:
                base_result = result
            else:
                base_result.merge_in(result)
            if i == total - 1:
                base_result.screenshot_path = take_screenshot(
                    page, "login", "page_load",
                )

    console.stop()

    if base_result is None:
        return

    base_result.compute_all()
    results_collector.append(base_result)

    logger.info(
        "Login page load (n=%d) — wall median: %.0f ms | P95: %.0f ms | TTFB: %.0f ms | errors: %d",
        measured_count,
        base_result.wall_clock.median,
        base_result.wall_clock.p95,
        base_result.ttfb.median,
        base_result.console_error_count,
    )


@pytest.mark.performance
def test_login_flow(
    unauthenticated_page: Page,
    results_collector: list,
) -> None:
    """Measure the full login flow: page load + credential entry + redirect.

    Reports two timings:
    - login_page_load_ms: navigation -> email input visible
    - login_submit_ms: start filling credentials -> post-login URL reached
    """
    page = unauthenticated_page
    username, password = _require_credentials()
    login_page = LoginPage(page)

    network_load = NetworkCapture()
    network_load.start(page)
    with measure_action("Login page load (pre-login)") as page_load_clock:
        page.goto(BASE_URL, wait_until="commit")
        login_page.wait_for_login_form()
    network_load.stop()

    network_login = NetworkCapture()
    network_login.start(page)
    with measure_action("Login credential submission") as login_clock:
        login_page.login(username, password)
        page.wait_for_url(f"{BASE_URL}/**", timeout=30_000)
    network_login.stop()

    screenshot_path = take_screenshot(page, "login", "post_login")

    page_load_result = MeasurementResult.from_wall_clock(
        "Login", "page_load", page_load_clock[0],
        network_capture=network_load,
    )
    login_result = MeasurementResult.from_wall_clock(
        "Login", "login_submit", login_clock[0],
        network_capture=network_login,
        screenshot_path=screenshot_path,
    )
    results_collector.append(page_load_result)
    results_collector.append(login_result)

    logger.info(
        "Login flow — page load: %.0f ms | login submit: %.0f ms | total: %.0f ms",
        page_load_result.wall_clock.median,
        login_result.wall_clock.median,
        page_load_result.wall_clock.median + login_result.wall_clock.median,
    )
