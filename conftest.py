import os
from typing import Generator

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page

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
        help="Reuse a single page (tab) across all tests instead of a fresh tab per test",
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
    pg = context.new_page()
    pg.goto(BASE_URL)

    login_page = LoginPage(pg)
    login_page.login(username, password)

    logger.info("Waiting for post-login navigation")
    pg.wait_for_url(f"{BASE_URL}/**", timeout=30_000)

    context.storage_state(path=AUTH_STATE_PATH)
    logger.info("Auth state saved to %s", AUTH_STATE_PATH)
    pg.close()
    context.close()


# ---------------------------------------------------------------------------
# Authenticated page — single browser window for the entire run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _auth_context(
    browser: Browser,
    browser_context_args: dict,
) -> Generator[BrowserContext, None, None]:
    """Session-scoped authenticated context — one browser window for all tests."""
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()


@pytest.fixture(scope="session")
def _shared_page(
    _auth_context: BrowserContext,
    request: pytest.FixtureRequest,
) -> Generator[Page | None, None, None]:
    """Session-scoped page reused across all tests (--single-session only)."""
    if not request.config.getoption("--single-session"):
        yield None
        return
    logger.info("Single-session mode: creating shared authenticated page")
    pg = _auth_context.new_page()
    yield pg
    pg.close()


@pytest.fixture()
def page(
    _shared_page: Page | None,
    _auth_context: BrowserContext,
) -> Generator[Page, None, None]:
    """Per-test authenticated page.

    --single-session : reuses the single session-scoped page (same tab).
    default          : opens a fresh tab inside the session-scoped context,
                       closed after the test.  The browser window stays open.
    """
    if _shared_page is not None:
        yield _shared_page
        return
    pg = _auth_context.new_page()
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Unauthenticated page — single browser window for the entire run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _unauth_context(
    browser: Browser,
) -> Generator[BrowserContext, None, None]:
    """Session-scoped unauthenticated context — one browser window."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture(scope="session")
def _shared_unauth_page(
    _unauth_context: BrowserContext,
    request: pytest.FixtureRequest,
) -> Generator[Page | None, None, None]:
    """Session-scoped unauth page reused across all tests (--single-session only)."""
    if not request.config.getoption("--single-session"):
        yield None
        return
    logger.info("Single-session mode: creating shared unauthenticated page")
    pg = _unauth_context.new_page()
    yield pg
    pg.close()


@pytest.fixture()
def unauthenticated_page(
    _shared_unauth_page: Page | None,
    _unauth_context: BrowserContext,
) -> Generator[Page, None, None]:
    """Per-test unauthenticated page for login benchmarking.

    --single-session : reuses the single session-scoped page (same tab).
    default          : opens a fresh tab, closed after the test.
    """
    if _shared_unauth_page is not None:
        yield _shared_unauth_page
        return
    pg = _unauth_context.new_page()
    yield pg
    pg.close()
