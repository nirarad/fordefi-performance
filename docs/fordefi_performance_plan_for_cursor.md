# Fordefi Preprod UI Performance Investigation Plan

## Objective

Build a Python + Playwright performance investigation framework for Fordefi preprod that supports:

- broad scan across prioritized product areas
- deep dive into selected hotspots
- evidence collection for report writing
- repeatable measurement mode
- benchmark mode against a previous baseline
- extension via page definitions with manually maintained `data-testid` selectors

This plan is optimized for a 4-5 hour take-home assignment.

---

## Assignment framing

The assignment asks for:

- a testing infrastructure and test suite for UI performance analysis
- prioritization of findings
- root-cause investigation for poor-performing flows
- flexibility and maintainability of the framework
- a performance investigation report with methodology, evidence, root-cause hypotheses, and recommendations

Source: uploaded assignment PDF.

---

## Priorities

### High priority

- Vaults
- Assets
- Accounts
- Transactions
- Allowances

### Medium priority

- Address Book
- Transaction Policy
- AML Policy

### Low priority

- User Management
- Settings

### Deep-dive targets

- Vaults
- Transactions
- Assets
- Transaction Policy

---

## Investigation goals

1. Measure user-visible performance of key pages and actions.
2. Identify the slowest flows and rank them by user impact.
3. Investigate likely causes using UI timings, network data, console errors, traces, screenshots, and HAR evidence.
4. Produce a report that is credible, structured, and easy to extend.
5. Keep implementation intentionally lean and reusable.

---

## Non-goals

- No synthetic load generation.
- No backend code instrumentation.
- No fixing product issues.
- No guessing selectors when stable `data-testid` values are unavailable.

If a required selector does not have a stable `data-testid`, stop and request manual instruction before continuing.

---

## Target environment

- **Base URL**: `https://app.preprod.fordefi.com/`
- **Role**: viewer (read-only access). The logged-in user cannot create, modify, or delete data. All tests observe existing data only.
- **Authentication**: username + password only. No MFA/2FA or additional auth steps are required for this user.

### Viewer role constraints

Because the account is read-only:

- Tests must **not** attempt write operations (create vault, send transaction, etc.)
- All scenarios are observation-only: page loads, table rendering, search, sort, filter, sidebar open
- If any UI element is disabled or hidden due to viewer permissions, skip it gracefully and log a note

---

## Authentication flow (CRITICAL - must be implemented)

The Fordefi preprod requires login before any page is accessible. Without authentication handling, no test can run. Login is username + password only (no MFA).

### Strategy: automated login + reusable `storageState`

Since login is simple username/password with no MFA, it can be fully automated:

1. **Automated login** via a setup script or a session-scoped fixture:
  - Navigate to the login page
  - Fill username and password from `.env`
  - Submit and wait for the dashboard to load
  - Save the authenticated browser state via `context.storage_state(path="auth/storage_state.json")`
2. **All subsequent tests reuse the saved state**:
  - Load `storage_state.json` into the browser context via pytest-playwright's `browser_context_args`
  - This skips login for every test, saving time and avoiding repeated login flows

### Implementation in conftest.py

```python
import os
from dotenv import load_dotenv

load_dotenv()

AUTH_STATE_PATH = "auth/storage_state.json"
BASE_URL = os.getenv("BASE_URL", "https://app.preprod.fordefi.com")

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
```

### Login helper script

Provide `scripts/save_auth_state.py` that automates login and saves session state. No manual interaction needed.

```python
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

def main():
    base_url = os.getenv("BASE_URL", "https://app.preprod.fordefi.com")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if not username or not password:
        raise ValueError("USERNAME and PASSWORD must be set in .env")

    os.makedirs("auth", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.goto(base_url)

        # Fill login form - adjust selectors after inspecting the actual login page
        page.get_by_label("Email").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Log in").click()

        # Wait for dashboard to confirm successful login
        page.wait_for_url("**/dashboard**", timeout=30_000)

        context.storage_state(path="auth/storage_state.json")
        browser.close()
        print("Auth state saved to auth/storage_state.json")

if __name__ == "__main__":
    main()
```

Note: the login form selectors above (`get_by_label("Email")`, etc.) are initial guesses. Adjust them after inspecting the actual Fordefi login page. If stable selectors are not obvious, use `page.pause()` to inspect interactively.

### Auth state management rules

- `auth/storage_state.json` must be in `.gitignore` (contains session tokens)
- If the state expires, re-run `python scripts/save_auth_state.py`
- Tests must detect expired auth (e.g. redirect to login page) and fail with a clear message, not hang
- Credentials are read from `.env` (never hardcoded)

---

## Recommended toolset

Use these as the primary toolchain.

### Core execution

- **Playwright for Python** via `pytest-playwright` for browser automation and test isolation.
- **Pytest parametrization** for DDT-style execution across pages, actions, and datasets via `@pytest.mark.parametrize`.

### pytest-playwright built-in fixtures and CLI flags (CRITICAL - use, do not reimplement)

`pytest-playwright` provides built-in fixtures: `page`, `context`, `browser`, `browser_name`, `browser_type`, `browser_context_args`. Do **not** override the `page` fixture unless strictly necessary - the default fixture already handles page lifecycle correctly.

Leverage these built-in CLI flags instead of writing custom options:

- `--browser chromium|firefox|webkit` - select browser
- `--headed` - visible browser (debugging only, never for measurement)
- `--base-url` - base URL for `page.goto("/relative")`
- `--tracing on|off|retain-on-failure` - Playwright traces
- `--screenshot on|off|only-on-failure` - screenshots
- `--video on|off|retain-on-failure` - record video
- `--output` - artifact output directory (default: `test-results/`)

Customize via `browser_context_args` fixture in conftest.py:

```python
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "record_har_path": "artifacts/har/trace.har",
    }
```

### Timeout configuration for performance measurement (CRITICAL)

Default Playwright timeouts auto-retry and mask actual slowness. For performance measurement:

- Use `page.wait_for_selector(selector, timeout=...)` with explicit timeouts as the measurement boundary
- Do **not** use auto-retrying `expect()` assertions as timing endpoints - they hide actual wait duration behind retry loops
- For navigation timing, use `page.goto(url, wait_until="networkidle")` or `"load"` depending on the target metric
- Set `page.set_default_timeout(30_000)` to prevent infinite hangs while keeping it large enough to capture real load durations

### Headless-by-default for measurement consistency

Performance measurements must run headless (Playwright default) for repeatable results. Headed mode introduces GPU compositing and window manager overhead. Reserve `--headed` for debugging only.

### Evidence and debugging

- **Playwright tracing** to capture interaction traces and open them in Trace Viewer. Use the built-in `--tracing retain-on-failure` flag.
- **Playwright network monitoring / HAR support** to inspect network traffic and preserve request evidence. Enable via `record_har_path` in `browser_context_args`.
- **Console error collection** through Playwright page event listeners.
- **Screenshots** for visual evidence. Use `--screenshot only-on-failure` for CI, explicit `page.screenshot()` for evidence collection.

### Benchmarking / audit augmentation

- **Lighthouse** for standardized page-level web performance auditing on selected pages. Note: Lighthouse requires Node.js and the `lighthouse` npm package - it is not a Python-native tool. Use only as a supplement, not the main framework. If Node.js is not available in the test environment, skip Lighthouse entirely and rely on the browser Performance API metrics captured via Playwright.

### Human-readable reporting

Choose one:

- **Allure Report** for rich interactive reporting, attachments, history, and trend analysis.
- **pytest-html** for a lighter HTML report if time is tight.

### Decision for this assignment

Implement:

- Playwright + pytest as the execution framework
- JSON/CSV results for machine-readable benchmark comparison
- markdown report for final submission
- optional pytest-html for quick local HTML output
- optional Allure only if setup time remains
- optional Lighthouse on 1-2 candidate pages only

Do **not** over-engineer report tooling at the expense of framework clarity.

---

## Architecture approach

Use a **capability-based model** for page behavior, backed by `Protocol` classes (structural subtyping) and `dataclass` configuration.

### Design principles

- pages declare **capabilities**, not custom procedural logic everywhere
- behavior modules execute generic actions against any page implementing the required interface
- selectors come from a single source of truth
- prefer `data-testid`; do not invent brittle selectors
- metrics, evidence, and benchmark outputs are standardized

### Page object conventions

Each page object module follows this structure:

1. **Selectors dataclass** — a frozen `@dataclass` at the top of the module holding all CSS/testid selector strings. Keeps selectors scannable and separated from logic.
2. **Page class** — references `selectors` as a class attribute. Locators that use `get_by_role` or other Playwright helpers (not raw CSS strings) are exposed as `@property` methods.
3. **Locator creation** — locators are created fresh on access (not cached in `__init__`). Playwright locators auto-wait and should resolve against the current DOM state.
4. **`@property` for element access** — use `@property` for locators that return a `Locator` object. This reads naturally: `self._continue_button.click()` instead of `self._continue_button().click()`.

Example:
```python
@dataclass(frozen=True)
class VaultsSelectors:
    table: str = "[data-testid='vaults-table']"
    search_input: str = "[data-testid='search-input']"

class VaultsPage:
    selectors = VaultsSelectors()

    def __init__(self, page: Page) -> None:
        self.page = page

    @property
    def _table(self) -> Locator:
        return self.page.locator(self.selectors.table)

    @property
    def _sort_by_name(self) -> Locator:
        return self.page.get_by_role("button", name="Name")
```

### Core interfaces (use `Protocol`)

Prefer `typing.Protocol` for page interfaces. Protocol enables structural subtyping (duck typing with type safety) which is more Pythonic and avoids forced inheritance hierarchies. Pages only need to implement the right methods/attributes - they don't need to inherit from a base class.

Define Protocol classes such as:

- `HasTable` - pages with table content (table_selector_testid, row_selector_testid)
- `Searchable` - pages with search (search_input_testid)
- `Sortable` - pages with sortable columns (sort_target_testid)
- `Filterable` - pages with filters (filter_trigger_testid)
- `Paginated` - pages with pagination
- `HasSidebar` - pages with detail sidebar

Example:

```python
from typing import Protocol

class HasTable(Protocol):
    table_selector_testid: str
    row_selector_testid: str

class Searchable(Protocol):
    search_input_testid: str

def measure_search(page: Page, spec: Searchable, term: str) -> float:
    ...
```

Fall back to `ABC` only if runtime enforcement of missing methods is needed during development.

### Page definition style

Use a dataclass-backed page spec with fields like:

- `name`
- `path`
- `priority`
- `deep_dive_candidate`
- `supports_table`
- `supports_spinner`
- `supports_progress_bar`
- `supports_search`
- `supports_sort`
- `supports_filter`
- `supports_pagination`
- `supports_sidebar`
- `search_fields`
- `default_sort_column`
- `default_filter_scenario`
- `ready_selector_testid`
- `table_selector_testid`
- `spinner_selector_testid`
- `progress_bar_selector_testid`
- `search_input_testid`
- `sort_target_testid`
- `filter_trigger_testid`
- `empty_state_testid`
- `row_selector_testid`

If any required selector is missing a stable `data-testid`, stop and request manual input.

---

## Repository structure

```text
fordefi-perf/
  README.md
  requirements.txt
  pytest.ini
  pyrightconfig.json
  .env.example
  conftest.py

  auth/
    storage_state.json   # gitignored, created by login helper

  scripts/
    save_auth_state.py   # one-time headed login helper

  configs/
    __init__.py
    pages.py
    thresholds.py

  core/
    __init__.py
    protocols.py
    metrics.py
    benchmark.py
    console_capture.py
    evidence.py
    timing.py
    network_capture.py
    report_writer.py

  pages/
    __init__.py
    vaults_page.py
    assets_page.py
    accounts_page.py
    transactions_page.py
    allowances_page.py
    address_book_page.py
    transaction_policy_page.py
    aml_policy_page.py
    user_management_page.py
    settings_page.py

  tests/
    __init__.py
    test_broad_scan.py
    test_deep_dive.py
    test_benchmark.py

  data/
    __init__.py
    scenario_loader.py
    scenarios/
      vaults.csv

  artifacts/
    screenshots/
    traces/
    har/
    json/
    csv/
    html/

  reports/
    performance_investigation_report.md
```

Note: every Python package directory must include an `__init__.py` file.

---

## Run modes

### Custom CLI option registration (CRITICAL)

Custom options like `--mode` and `--baseline` must be registered via `pytest_addoption` in conftest.py. Without this, pytest will reject unknown flags.

```python
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
```

### 1. Measure mode

Purpose:

- execute flows
- capture metrics and evidence
- generate a fresh baseline

Outputs:

- `results.json`
- `results.csv`
- screenshots
- traces
- console-errors JSON/text
- optional HAR captures
- optional HTML report

CLI shape:

```bash
pytest -m performance --mode=measure
```

### 2. Benchmark mode

Purpose:

- compare current results against previous baseline
- identify regressions and improvements

Inputs:

- previous `results.json`

Outputs:

- benchmark diff JSON/CSV
- regression summary markdown

CLI shape:

```bash
pytest -m benchmark --mode=benchmark --baseline=artifacts/json/baseline.json
```

### Benchmark logic

For each comparable metric:

- absolute delta
- percentage delta
- status: improved / unchanged / regressed

Suggested default regression threshold:

- warning: >10%
- critical: >20%

---

## Metrics to capture

### Browser-native Performance API metrics (CRITICAL)

Use the browser's built-in Performance API as the primary source of navigation timing, not only Python-side stopwatch measurements. Playwright can access these via `page.evaluate()`.

Capture from `PerformanceNavigationTiming`:

- `domContentLoadedEventEnd` - DOM ready
- `loadEventEnd` - full page load
- `responseEnd - requestStart` - server response time (TTFB)
- `domInteractive` - time to interactive DOM

Capture Core Web Vitals via PerformanceObserver injection:

- **LCP** (Largest Contentful Paint) - primary load metric
- **CLS** (Cumulative Layout Shift) - visual stability
- **INP** (Interaction to Next Paint) - responsiveness to user input

Example capture pattern:

```python
nav_timing = page.evaluate("""() => {
    const entry = performance.getEntriesByType('navigation')[0]
    return {
        ttfb: entry.responseStart - entry.requestStart,
        dom_content_loaded: entry.domContentLoadedEventEnd,
        load_event_end: entry.loadEventEnd,
        dom_interactive: entry.domInteractive,
    }
}""")
```

### Custom page-level metrics

- navigation start timestamp (Python-side `time.perf_counter()`)
- page-ready timestamp (custom `data-testid` selector visible)
- table-ready timestamp
- spinner duration
- progress-bar duration
- total visible load time
- row count on loaded table
- console error count

### Interaction-level metrics

- sort start -> sort complete
- filter start -> filter complete
- search start -> search complete
- pagination click -> page stable
- sidebar open start -> sidebar visible

### Statistical rigor (CRITICAL)

Raw single-sample measurements are not credible for performance reporting. Apply the following:

- **Minimum iterations**: run each flow at least 5 times for broad scan, 10+ for deep dives
- **Warm-up run**: discard the first iteration to avoid cold-start skew (browser cache, JIT, DNS)
- **Aggregation**: report median, P95, P99, min, max, and standard deviation
- **Outlier detection**: flag runs where timing deviates >2x standard deviation from the median
- Use `statistics.median`, `statistics.stdev` from the Python standard library

Example aggregation structure:

```python
@dataclass
class AggregatedMetric:
    name: str
    samples: list[float]
    median: float
    p95: float
    p99: float
    std_dev: float
    min: float
    max: float
```

### Evidence fields

- page name
- action name
- dataset / parameter set
- browser timestamp
- screenshot path
- trace path
- HAR path if relevant
- console errors captured during step
- notes / anomaly tags

---

## Console error handling

This is required.

Capture all browser console messages during each flow, then classify them into:

- `error`
- `warning`
- `info`

Store at minimum:

- message type
- text
- page URL
- timestamp

Report:

- total console errors by page
- repeated error signatures
- whether errors correlate with slow flows

A high volume of console errors should be explicitly called out in the final report.

---

## Test strategy

### Broad scan

Cover all scoped pages with lightweight measurement.

For each page, execute only actions supported by that page's declared interface/capabilities:

1. open page
2. wait for ready state
3. measure initial load
4. if searchable: run search
5. if sortable: run sort
6. if filterable: run filter
7. if paginated: inspect first pagination interaction
8. collect console errors
9. save screenshot and metrics

Output:

- ranked hotspot inventory
- candidate pages for deep dive

### Deep dive

Run on:

- Vaults
- Transactions
- Assets
- Transaction Policy

For each deep-dive page:

- repeat the key flows multiple times (minimum 10 iterations, discard first warm-up run)
- preserve trace and screenshots
- preserve network evidence where relevant
- compare timings across runs with statistical aggregation (median, P95, std dev)
- correlate visible slowness with console/network signals

### DDT / parametrized execution (CSV-driven)

Test data lives in CSV files under `data/scenarios/`, one file per page (e.g. `vaults.csv`). Tests load scenarios at collection time via `data/scenario_loader.py` and feed them into `pytest.mark.parametrize`.

CSV format:
```csv
action,param_key,param_value,expect_results
search,term,My Vault,true
search,term,nonexistent_xyz,false
sort,column_testid,vault-name-column,asc
filter,filter_testid,chain-filter,ethereum
```

Lines starting with `#` are treated as comments and skipped.

`scenario_loader.py` provides:
- `load_scenarios(page_name)` — all rows from `data/scenarios/<page_name>.csv`
- `load_scenarios_by_action(page_name, action)` — filtered to a single action type

Example parametrize usage:
```python
from data.scenario_loader import load_scenarios

@pytest.mark.parametrize(
    "scenario",
    load_scenarios("vaults"),
    ids=lambda s: s.test_id,
)
def test_vaults_interaction(page, scenario):
    ...
```

Keep CSV data small and intentional. Do **not** define scenario data in Python code — all DDT data belongs in CSV.

---

## Suggested scenarios

### High priority pages

#### Vaults

- load page
- wait for table
- search by name/address
- sort key column
- apply filter if available

#### Assets

- load page
- wait for assets table
- search
- sort
- filter

#### Accounts

- load page
- wait for accounts table
- search
- sort
- filter

#### Transactions

- load page
- wait for transactions table
- search by name/address if supported
- sort
- filter
- optional sidebar open if stable selector exists

#### Allowances

- load page
- wait for list
- search / sort / filter where supported

### Medium priority pages

#### Address Book

- load page
- wait for table
- search by name/address
- sort
- filter if present

#### Transaction Policy

- load page
- measure top progress bar duration
- measure list/table ready state
- search if present
- sort/filter if supported
- explicitly note lack of pagination

#### AML Policy

- load page
- wait for rules list
- search/sort/filter where supported

### Low priority pages

Smoke-only pass unless very fast to implement.

---

## Root-cause investigation heuristics

Use these heuristics in the report, but mark them as hypotheses unless directly evidenced.

### Likely bottleneck classes

- missing pagination / large unbounded list
- expensive server-side sort/filter/search
- repeated or redundant API calls
- heavy client-side rendering on large datasets
- console errors causing degraded UX or retries
- slow page transition with weak loading-state UX

### Correlation rules

- slow action + slow network timing => likely API/backend bottleneck
- slow action + fast network + delayed render => likely frontend rendering bottleneck
- repeated requests after single action => possible duplicate fetch / state churn
- large console error volume around slow action => potential broken rendering path or failed requests

---

## Output artifacts

Generate these artifacts for each run:

- `artifacts/json/results.json`
- `artifacts/csv/results.csv`
- `artifacts/json/console_errors.json`
- `artifacts/screenshots/...`
- `artifacts/traces/...zip`
- `artifacts/har/...har` for selected flows only
- `reports/performance_investigation_report.md`

---

## Final report structure

```text
1. Executive Summary
2. Methodology
3. Scope and Coverage
4. Framework Design
5. Broad Scan Results
6. Deep-Dive Investigations
7. Console Error Analysis
8. Prioritized Findings
9. Root-Cause Hypotheses
10. Recommendations
11. Benchmark/Regression Design
12. Extensibility / How to Add New Test Cases
13. Appendix: Screenshots, Traces, HAR references
```

### Report requirements mapping

Ensure the report explicitly covers:

- methodology
- scope / coverage
- issue descriptions
- issue prioritization
- evidence and investigation details
- possible root cause
- suggested improvement / solution
- explanation of how to add new test cases

This aligns directly with the assignment deliverable requirements.

---

## Extensibility rules

1. Every new page must be added through a page spec + Protocol implementation.
2. Use `data-testid` selectors where possible.
3. Do not create brittle CSS/XPath fallbacks silently.
4. If a stable selector does not exist, stop and request manual guidance.
5. Test IDs are assumed to be manually maintained outside the framework.
6. New test cases should be added by extending page specs and scenario data, not by duplicating procedural code.

## No selectors in tests (CRITICAL)

Test files must **never** reference CSS selectors, XPath expressions, `data-testid` strings, or call `page.locator()` directly. All DOM interaction must go through page object methods.

### What belongs in page objects

- Selector strings (in `Selectors` dataclass or `TabConfig`)
- `page.locator()` calls
- `wait_for_selector()` calls
- Any DOM query or element interaction logic

### What belongs in tests

- Page object method calls (`nav_page.navigate_to()`, `login_page.wait_for_login_form()`)
- URL navigation (`page.goto()`, `page.wait_for_url()`)
- Timing wrappers (`measure_action`)
- Metric capture (`capture_navigation_timing`, `capture_web_vitals`)
- Evidence capture (`take_screenshot`)
- Assertions and logging

### Why

- Selector changes only require updating one place (the page object), not every test
- Tests read as high-level intent, not DOM implementation details
- Consistent timeout and wait strategies are enforced in page objects, not scattered across tests

---

## Implementation order

This is the execution order Cursor should follow.

### Phase 1 - Bootstrap

1. Create repository skeleton (including `__init__.py` in all package directories).
2. Add dependencies.
3. Configure Playwright + pytest (register custom CLI options via `pytest_addoption`).
4. Add `.env.example` for credentials/base URL (`https://app.preprod.fordefi.com`).
5. Add artifact output folders.
6. Create `scripts/save_auth_state.py` login helper.
7. Create `auth/` directory and add `auth/storage_state.json` to `.gitignore`.
8. Configure `browser_context_args` to load `storage_state.json` and set `base_url`.
9. Do **not** override the built-in `page` fixture from pytest-playwright.

### Phase 2 - Core framework

1. Implement Protocol-based capability interfaces (in `core/protocols.py`).
2. Implement dataclass page spec model.
3. Implement generic timing utilities (both `time.perf_counter()` and browser Performance API capture).
4. Implement console capture.
5. Implement evidence capture.
6. Implement JSON/CSV result writer (use Python `json` and `csv` stdlib - no pandas needed).
7. Implement benchmark comparator.
8. Implement statistical aggregation (median, P95, P99, std dev).

### Phase 3 - Page definitions

1. Add page specs for all scoped pages.
2. Populate only selectors with stable `data-testid` values.
3. If a required selector is missing, stop and request user input.

### Phase 4 - Test flows

1. Implement broad scan test.
2. Implement deep-dive test (with iteration loops and warm-up).
3. Implement DDT parameter sets.
4. Implement benchmark test.

### Phase 5 - Reporting

1. Generate markdown report from result artifacts.
2. Summarize hotspots and deep-dive findings.
3. Include console error analysis.
4. Include benchmark design and extension instructions.

---

## Minimal dependency suggestion

```text
playwright
pytest
pytest-playwright
pytest-html
python-dotenv
```

Notes:

- Use Python `dataclasses` from stdlib. Avoid `pydantic` unless validation complexity warrants it.
- Use Python `json`, `csv`, `statistics` from stdlib. Do **not** add `pandas` - it is unnecessary overhead for this scope.
- Use `pytest-base-url` only if `--base-url` flag is not already provided by `pytest-playwright`.

Optional:

```text
allure-pytest
```

Avoid unnecessary stack expansion.

---

## Logging (MUST use — no print statements)

All modules must use Python's built-in `logging` module. **Never use `print()` for status, progress, or diagnostic output.** This applies to test code, core framework modules, and scripts.

### Setup

Configure a project-wide logger in `core/logger.py`:

```python
import logging
import sys

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
```

### Usage in every module

```python
from core.logger import get_logger

logger = get_logger(__name__)

logger.info("Navigating to %s", page_spec.path)
logger.warning("Selector %s not found, skipping", testid)
logger.error("Auth state expired — redirected to login page")
logger.debug("Raw timing samples: %s", samples)
```

### Rules

- Each module gets its own logger via `get_logger(__name__)`.
- Use `logger.info` for test flow progress (page loaded, measurement complete, artifact saved).
- Use `logger.warning` for non-fatal issues (missing optional selector, skipped action).
- Use `logger.error` for failures (auth expired, timeout exceeded, assertion failed).
- Use `logger.debug` for verbose data (raw samples, full response bodies) — off by default.
- pytest captures log output automatically. Use `--log-cli-level=INFO` to see logs during test runs.
- Scripts (`save_auth_state.py`, etc.) must also use `get_logger`, not `print()`.

---

## Coding constraints for Cursor

- Use Python only.
- **Use `logging` for all output. Never use `print()`.**
- Keep implementation pragmatic, not enterprise-heavy.
- Prefer `Protocol` for interfaces. Fall back to `ABC` only when runtime enforcement is needed.
- Prefer small modules and explicit type hints.
- Avoid speculative abstractions.
- No selector guessing when `data-testid` is missing.
- Preserve artifacts deterministically with timestamped file names.
- Write code and report output suitable for take-home submission, not production deployment.
- Do **not** override pytest-playwright's built-in `page` fixture unless there is a specific, documented reason.
- Always measure in headless mode for consistency. Use `--headed` for debugging only.

---

## Done criteria

The task is complete when all of the following exist:

1. Authentication flow: `scripts/save_auth_state.py` + `storage_state.json` reuse in `browser_context_args`.
2. Reusable Python + Playwright framework with Protocol-based page model.
3. Broad scan covering scoped pages (all tests run as viewer against `https://app.preprod.fordefi.com`).
4. Deep-dive coverage for vaults, transactions, assets, transaction policy.
5. DDT-based execution.
6. Measure mode and benchmark mode (with `pytest_addoption` registration).
7. Console error capture integrated into results.
8. Browser Performance API metrics (navigation timing, Core Web Vitals) captured alongside custom timings.
9. Statistical aggregation of multi-iteration measurements (median, P95, std dev).
10. JSON/CSV artifacts.
11. Markdown investigation report.
12. Clear extension instructions for adding new pages and test cases.

