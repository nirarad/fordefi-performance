import os

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Browser

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

    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    if not username or not password:
        pytest.fail(
            "No auth state found and USERNAME/PASSWORD not set in .env. "
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
