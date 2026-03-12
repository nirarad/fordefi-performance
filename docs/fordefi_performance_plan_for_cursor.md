# Fordefi Preprod UI Performance Investigation Plan

## Objective
Build a Python + Playwright performance investigation framework for Fordefi preprod that supports:
- broad scan across prioritized product areas
- deep dive into selected hotspots
- evidence collection for report writing
- repeatable measurement mode
- benchmark mode against a previous baseline
- extension via page definitions with manually maintained `data-testid` selectors

This plan is optimized for a 4–5 hour take-home assignment.

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

## Recommended toolset
Use these as the primary toolchain.

### Core execution
- **Playwright for Python** via `pytest-playwright` for browser automation and test isolation. Playwright recommends the official Playwright Pytest plugin. citeturn547720search12
- **Pytest parametrization** for DDT-style execution across pages, actions, and datasets. Pytest supports `@pytest.mark.parametrize` for running the same test with multiple inputs. citeturn199733search2turn199733search15

### Evidence and debugging
- **Playwright tracing** to capture interaction traces and open them in Trace Viewer. citeturn547720search0turn547720search4
- **Playwright network monitoring / HAR support** to inspect network traffic and preserve request evidence. Playwright supports network tracking and HAR recording/replay flows. citeturn547720search13turn547720search9turn547720search5
- **Console error collection** through Playwright page event listeners.
- **Screenshots** for visual evidence.

### Benchmarking / audit augmentation
- **Lighthouse** for standardized page-level web performance auditing and regression-oriented comparison on selected pages. Lighthouse audits a URL and generates a performance report; Lighthouse CI is intended to prevent regressions. Use this only as a supplement to the Playwright investigation, not as the main framework. citeturn547720search2turn547720search10

### Human-readable reporting
Choose one:
- **Allure Report** for rich interactive reporting, attachments, history, and trend analysis. Allure supports pytest integration, attachments, history, timeline, and visual analytics. citeturn547720search3turn547720search11turn547720search15
- **pytest-html** for a lighter HTML report if time is tight. It supports HTML reports and extra embedded content such as JSON, text, URLs, and images. citeturn199733search1turn199733search3

### Decision for this assignment
Implement:
- Playwright + pytest as the execution framework
- JSON/CSV results for machine-readable benchmark comparison
- markdown report for final submission
- optional pytest-html for quick local HTML output
- optional Allure only if setup time remains
- optional Lighthouse on 1–2 candidate pages only

Do **not** over-engineer report tooling at the expense of framework clarity.

---

## Architecture approach
Use an **interface-style model** for page behavior, backed by `ABC` and `dataclass` configuration.

### Design principles
- pages declare **capabilities**, not custom procedural logic everywhere
- behavior modules execute generic actions against any page implementing the required interface
- selectors come from a single source of truth
- prefer `data-testid`; do not invent brittle selectors
- metrics, evidence, and benchmark outputs are standardized

### Core interfaces
Create abstract interfaces such as:
- `BasePage`
- `TablePage`
- `SearchablePage`
- `SortablePage`
- `FilterablePage`
- `PaginatedPage`
- `SidebarPage`
- `ConsoleObservablePage`

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
  .env.example
  conftest.py

  configs/
    pages.py
    scenarios.py
    thresholds.py

  core/
    base_page.py
    capabilities.py
    metrics.py
    benchmark.py
    console_capture.py
    evidence.py
    timing.py
    network_capture.py
    report_writer.py

  pages/
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
    test_broad_scan.py
    test_deep_dive.py
    test_benchmark.py

  data/
    datasets.py

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

---

## Run modes

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
pytest -m measure --mode=measure
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

### Page-level metrics
- navigation start timestamp
- page-ready timestamp
- table-ready timestamp
- spinner duration
- progress-bar duration
- total visible load time
- row count on loaded table
- console error count

### Interaction-level metrics
- sort start → sort complete
- filter start → filter complete
- search start → search complete
- pagination click → page stable
- sidebar open start → sidebar visible

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

For each page, execute only actions supported by that page’s declared interface/capabilities:
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
- repeat the key flows multiple times
- preserve trace and screenshots
- preserve network evidence where relevant
- compare timings across runs
- correlate visible slowness with console/network signals

### DDT / parametrized execution
Use `pytest.mark.parametrize` to drive:
- page under test
- action type
- search term set
- filter scenario
- sort scenario
- run mode

Example dimensions:
- pages: vaults, assets, accounts, transactions, allowances, address_book, transaction_policy, aml_policy
- actions: load, search, sort, filter
- datasets: name-based search, address-based search, empty-result search, common filter, common sort

Keep DDT data small and intentional.

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
1. Every new page must be added through a page spec + interface implementation.
2. Use `data-testid` selectors where possible.
3. Do not create brittle CSS/XPath fallbacks silently.
4. If a stable selector does not exist, stop and request manual guidance.
5. Test IDs are assumed to be manually maintained outside the framework.
6. New test cases should be added by extending page specs and scenario data, not by duplicating procedural code.

---

## Implementation order
This is the execution order Cursor should follow.

### Phase 1 — Bootstrap
1. Create repository skeleton.
2. Add dependencies.
3. Configure Playwright + pytest.
4. Add `.env.example` for credentials/base URL.
5. Add artifact output folders.

### Phase 2 — Core framework
6. Implement base interfaces with `ABC`.
7. Implement dataclass page spec model.
8. Implement generic timing utilities.
9. Implement console capture.
10. Implement evidence capture.
11. Implement JSON/CSV result writer.
12. Implement benchmark comparator.

### Phase 3 — Page definitions
13. Add page specs for all scoped pages.
14. Populate only selectors with stable `data-testid` values.
15. If a required selector is missing, stop and request user input.

### Phase 4 — Test flows
16. Implement broad scan test.
17. Implement deep-dive test.
18. Implement DDT parameter sets.
19. Implement benchmark test.

### Phase 5 — Reporting
20. Generate markdown report from result artifacts.
21. Summarize hotspots and deep-dive findings.
22. Include console error analysis.
23. Include benchmark design and extension instructions.

---

## Minimal dependency suggestion

```text
playwright
pytest
pytest-playwright
pytest-html
pydantic or dataclasses-only approach
pandas
python-dotenv
```

Optional:
```text
allure-pytest
```

Avoid unnecessary stack expansion.

---

## Coding constraints for Cursor
- Use Python only.
- Keep implementation pragmatic, not enterprise-heavy.
- Prefer small modules and explicit types.
- Avoid speculative abstractions.
- No selector guessing when `data-testid` is missing.
- Preserve artifacts deterministically with timestamped file names.
- Write code and report output suitable for take-home submission, not production deployment.

---

## Done criteria
The task is complete when all of the following exist:
1. Reusable Python + Playwright framework with interface-style page model.
2. Broad scan covering scoped pages.
3. Deep-dive coverage for vaults, transactions, assets, transaction policy.
4. DDT-based execution.
5. Measure mode and benchmark mode.
6. Console error capture integrated into results.
7. JSON/CSV artifacts.
8. Markdown investigation report.
9. Clear extension instructions for adding new pages and test cases.

