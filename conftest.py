import os
from typing import Generator

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, Page

from core.logger import get_logger
from pages.login_page import LoginPage

load_dotenv()

logger = get_logger(__name__)

AUTH_STATE_PATH = "auth/storage_state.json"
BASE_URL = os.getenv("BASE_URL", "https://app.preprod.fordefi.com")


def pytest_addoption(parser):
    parser.addoption(
        "--mode",
        action="store",
        default="measure",
        choices=["measure", "benchmark"],
        help="Run mode: measure (collect data) or benchmark (compare to baseline)",
    )
    parser.addoption(
        "--baseline",
        action="store",
        default=None,
        help="Path to baseline results JSON for benchmark mode",
    )
    parser.addoption(
        "--single-session",
        action="store_true",
        default=False,
        help="Reuse one browser context for all tests (no per-test isolation)",
    )


@pytest.fixture(scope="session")
def run_mode(request):
    return request.config.getoption("--mode")


@pytest.fixture(scope="session")
def baseline_path(request):
    return request.config.getoption("--baseline")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    context_args = {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "base_url": BASE_URL,
    }
    if os.path.exists(AUTH_STATE_PATH):
        context_args["storage_state"] = AUTH_STATE_PATH
    return context_args


@pytest.fixture(scope="session", autouse=True)
def ensure_authenticated(browser: Browser) -> None:
    """Log in and save storage state if it doesn't already exist."""
    if os.path.exists(AUTH_STATE_PATH):
        logger.info("Using saved auth state: %s", AUTH_STATE_PATH)
        return

    username = os.getenv("FORDEFI_USERNAME")
    password = os.getenv("FORDEFI_PASSWORD")
    if not username or not password:
        pytest.fail(
            "No auth state found and FORDEFI_USERNAME/FORDEFI_PASSWORD not set in .env. "
            "Run 'python scripts/save_auth_state.py' or set credentials."
        )

    logger.info("No auth state found — logging in to create one")
    os.makedirs("auth", exist_ok=True)
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.goto(BASE_URL)

    login_page = LoginPage(page)
    login_page.login(username, password)

    logger.info("Waiting for post-login navigation")
    page.wait_for_url(f"{BASE_URL}/**", timeout=30_000)

    context.storage_state(path=AUTH_STATE_PATH)
    logger.info("Auth state saved to %s", AUTH_STATE_PATH)
    page.close()
    context.close()


@pytest.fixture(scope="session")
def _shared_page(
    browser: Browser,
    browser_context_args: dict,
    request: pytest.FixtureRequest,
) -> Generator[Page | None, None, None]:
    """Session-scoped authenticated page, created only in --single-session mode."""
    if not request.config.getoption("--single-session"):
        yield None
        return
    logger.info("Single-session mode: creating shared authenticated context")
    context = browser.new_context(**browser_context_args)
    pg = context.new_page()
    yield pg
    pg.close()
    context.close()


@pytest.fixture(scope="session")
def _shared_unauth_page(
    browser: Browser,
    request: pytest.FixtureRequest,
) -> Generator[Page | None, None, None]:
    """Session-scoped unauthenticated page, created only in --single-session mode."""
    if not request.config.getoption("--single-session"):
        yield None
        return
    logger.info("Single-session mode: creating shared unauthenticated context")
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    pg = context.new_page()
    yield pg
    pg.close()
    context.close()


@pytest.fixture()
def page(
    browser: Browser,
    browser_context_args: dict,
    _shared_page: Page | None,
) -> Generator[Page, None, None]:
    """Override pytest-playwright's page fixture to support --single-session."""
    if _shared_page is not None:
        yield _shared_page
        return
    context = browser.new_context(**browser_context_args)
    pg = context.new_page()
    yield pg
    pg.close()
    context.close()


@pytest.fixture()
def unauthenticated_page(
    browser: Browser,
    _shared_unauth_page: Page | None,
) -> Generator[Page, None, None]:
    """Provide a page with no saved session for login benchmarking.

    In --single-session mode the same page is reused across login tests.
    Note: tests run in order, so later tests see state left by earlier ones
    (e.g. an authenticated session after test_login_flow completes).
    """
    if _shared_unauth_page is not None:
        yield _shared_unauth_page
        return
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    pg = context.new_page()
    yield pg
    pg.close()
    context.close()
