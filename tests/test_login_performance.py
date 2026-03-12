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
from core.timing import capture_navigation_timing, capture_web_vitals, measure_action
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
def test_login_page_load(unauthenticated_page: Page) -> None:
    """Measure time to load and render the Auth0 login page.

    Clock starts at navigation and stops when the email input is visible.
    """
    page = unauthenticated_page
    login_page = LoginPage(page)

    console = ConsoleCapture()
    console.start(page)

    with measure_action("Login page load") as wall_clock:
        page.goto(BASE_URL, wait_until="commit")
        form_ready_ms = login_page.wait_for_login_form()

    nav = capture_navigation_timing(page)
    vitals = capture_web_vitals(page)
    screenshot_path = take_screenshot(page, "login", "page_load")
    console.stop()

    result = MeasurementResult.from_page_load(
        "Login",
        "page_load",
        wall_clock[0],
        nav,
        vitals,
        console=console,
        screenshot_path=screenshot_path,
    )

    logger.info(
        "Login page load — wall: %.0f ms | form ready: %.0f ms | TTFB: %.0f ms | errors: %d",
        result.wall_clock.median,
        form_ready_ms,
        result.ttfb.median,
        result.console_error_count,
    )


@pytest.mark.performance
def test_login_flow(unauthenticated_page: Page) -> None:
    """Measure the full login flow: page load + credential entry + redirect.

    Reports two timings:
    - login_page_load_ms: navigation -> email input visible
    - login_submit_ms: start filling credentials -> post-login URL reached
    """
    page = unauthenticated_page
    username, password = _require_credentials()
    login_page = LoginPage(page)

    with measure_action("Login page load (pre-login)") as page_load_clock:
        page.goto(BASE_URL, wait_until="commit")
        login_page.wait_for_login_form()

    with measure_action("Login credential submission") as login_clock:
        login_page.login(username, password)
        page.wait_for_url(f"{BASE_URL}/**", timeout=30_000)

    screenshot_path = take_screenshot(page, "login", "post_login")

    page_load_result = MeasurementResult.from_wall_clock(
        "Login", "page_load", page_load_clock[0],
    )
    login_result = MeasurementResult.from_wall_clock(
        "Login", "login_submit", login_clock[0], screenshot_path=screenshot_path,
    )

    logger.info(
        "Login flow — page load: %.0f ms | login submit: %.0f ms | total: %.0f ms",
        page_load_result.wall_clock.median,
        login_result.wall_clock.median,
        page_load_result.wall_clock.median + login_result.wall_clock.median,
    )
