import os

import pytest
from dotenv import load_dotenv

load_dotenv()

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
