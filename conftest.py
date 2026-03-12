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

# Key used on pytest config to store collected performance results (list of MeasurementResult).
PERF_RESULTS_ATTR = "_fordefi_perf_results"


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
def results_collector(request):
    """Session-scoped list for performance test results. Stored on config for sessionfinish hook."""
    collected = []
    setattr(request.config, PERF_RESULTS_ATTR, collected)
    yield collected


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
# Authenticated page
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _auth_context_session(
    browser: Browser,
    browser_context_args: dict,
) -> Generator[BrowserContext, None, None]:
    """One authenticated browser context for the whole run (used with --single-session)."""
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()
    logger.info("Closed authenticated session context")


@pytest.fixture(scope="module")
def _auth_context_module(
    browser: Browser,
    browser_context_args: dict,
) -> Generator[BrowserContext, None, None]:
    """One authenticated browser context per test file — closed when the file ends."""
    context = browser.new_context(**browser_context_args)
    yield context
    context.close()
    logger.info("Closed authenticated context")


@pytest.fixture()
def page(
    request: pytest.FixtureRequest,
) -> Generator[Page, None, None]:
    """Per-test authenticated page (tab).

    --single-session : same browser context and tab for all tests (session-scoped).
    default          : one context per test file, fresh tab per test, closed afterwards.
    """
    if request.config.getoption("--single-session"):
        ctx = request.getfixturevalue("_auth_context_session")
    else:
        ctx = request.getfixturevalue("_auth_context_module")
    if request.config.getoption("--single-session"):
        if not hasattr(ctx, "_shared_page"):
            ctx._shared_page = ctx.new_page()  # type: ignore[attr-defined]
        yield ctx._shared_page  # type: ignore[attr-defined]
        return
    pg = ctx.new_page()
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Unauthenticated page
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _unauth_context_session(browser: Browser) -> Generator[BrowserContext, None, None]:
    """One unauthenticated browser context for the whole run (used with --single-session)."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()
    logger.info("Closed unauthenticated session context")


@pytest.fixture(scope="module")
def _unauth_context_module(browser: Browser) -> Generator[BrowserContext, None, None]:
    """One unauthenticated browser context per test file — closed when the file ends."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    yield context
    context.close()
    logger.info("Closed unauthenticated context")


@pytest.fixture()
def unauthenticated_page(request: pytest.FixtureRequest) -> Generator[Page, None, None]:
    """Per-test unauthenticated page for login benchmarking.

    --single-session : same browser context and tab for all tests (session-scoped).
    default          : one context per test file, fresh tab per test, closed afterwards.
    """
    if request.config.getoption("--single-session"):
        ctx = request.getfixturevalue("_unauth_context_session")
    else:
        ctx = request.getfixturevalue("_unauth_context_module")
    if request.config.getoption("--single-session"):
        if not hasattr(ctx, "_shared_page"):
            ctx._shared_page = ctx.new_page()  # type: ignore[attr-defined]
        yield ctx._shared_page  # type: ignore[attr-defined]
        return
    pg = ctx.new_page()
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Session finish: write artifacts and report (measure / benchmark)
# ---------------------------------------------------------------------------

def pytest_sessionfinish(session, exitstatus):
    """After all tests: write results JSON/CSV and markdown report (measure) or compare to baseline (benchmark)."""
    results = getattr(session.config, PERF_RESULTS_ATTR, None)
    if results is None or len(results) == 0:
        return

    run_mode = session.config.getoption("--mode", default="measure")
    baseline_path = session.config.getoption("--baseline", default=None)

    from core.report_writer import (
        write_benchmark_diff_csv,
        write_benchmark_diff_json,
        write_csv,
        write_html_report,
        write_json,
    )

    json_path = ""
    csv_path = ""

    if run_mode == "measure":
        json_path = write_json(results)
        csv_path = write_csv(results)
        write_html_report(
            results,
            comparison=None,
            json_path=json_path,
            csv_path=csv_path,
            run_mode=run_mode,
        )
        return

    if run_mode == "benchmark" and baseline_path:
        from core.benchmark import compare_results, comparison_to_dict, load_baseline
        try:
            baseline = load_baseline(baseline_path)
        except FileNotFoundError as e:
            logger.error("Benchmark baseline not found: %s", e)
            return
        current_dicts = [r.to_dict() for r in results]
        comparisons = compare_results(baseline, current_dicts)
        diff_data = comparison_to_dict(comparisons)
        write_benchmark_diff_json(diff_data)
        write_benchmark_diff_csv(diff_data)
        write_html_report(
            results,
            comparison=comparisons,
            json_path=json_path,
            csv_path=csv_path,
            run_mode=run_mode,
        )
    elif run_mode == "benchmark":
        logger.warning("Benchmark mode set but --baseline not provided; writing measure outputs only.")
        json_path = write_json(results)
        csv_path = write_csv(results)
        write_html_report(
            results,
            comparison=None,
            json_path=json_path,
            csv_path=csv_path,
            run_mode=run_mode,
        )
