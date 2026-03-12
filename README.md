# Fordefi Performance Tests

Playwright + Pytest framework for measuring front-end performance of the Fordefi web app.

## Prerequisites

- Python 3.11+
- Git

## Setup

```bash
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `BASE_URL` | Target app URL (default: `https://app.preprod.fordefi.com`) |
| `FORDEFI_USERNAME` | Login email address |
| `FORDEFI_PASSWORD` | Login password |

## Authentication

On the first run, the framework logs in automatically using the `.env` credentials and saves the session to `auth/storage_state.json`. Subsequent runs reuse that file and skip login.

To manually regenerate the auth state:

```bash
python scripts/save_auth_state.py
```

To force a fresh login, delete the saved state:

```bash
# Windows
del auth\storage_state.json

# macOS / Linux
rm auth/storage_state.json
```

## Running tests

### All performance tests

```bash
pytest
```

### Specific test files

```bash
# Nav-tab load (all tabs)
pytest tests/test_nav_tab_load.py

# Pagination only
pytest tests/test_nav_tab_load.py -m pagination

# Login benchmarks
pytest tests/test_login_performance.py
```

### By marker

```bash
pytest -m performance
pytest -m smoke
```

### Headed mode (visible browser)

```bash
pytest --headed
```

## Custom options

| Flag | Description |
|---|---|
| `--single-session` | Reuse one browser context across all tests instead of creating a fresh one per test. Reduces overhead but removes per-test isolation. |
| `--mode measure` | *(default)* Collect performance data. |
| `--mode benchmark` | Compare results against a baseline. |
| `--baseline PATH` | Path to a baseline JSON file (used with `--mode benchmark`). |
| `--iterations N` | Number of times to run each performance flow, including warmup (default: `1`). Use e.g. `11` for deep-dive (1 warmup + 10 measured). |
| `--warmup N` | Number of initial iterations to discard as warm-up (default: `0`). Use e.g. `1` with `--iterations 11`. |
| `--headed` | Run with a visible browser window (Playwright built-in). |
| `--browser chromium\|firefox\|webkit` | Choose browser engine (Playwright built-in, default: `chromium`). |

### Examples

```bash
# Quick headed run, single session
pytest tests/test_nav_tab_load.py --headed --single-session

# Deep-dive: 10 measured runs per flow (1 warmup discarded), statistical aggregation (median, P95, std dev)
pytest -m performance --iterations 11 --warmup 1

# Single tab with 3 iterations, 1 warmup
pytest tests/test_nav_tab_load.py -k "Vaults" --iterations 3 --warmup 1 --headed

# Benchmark against a previous baseline
pytest --mode benchmark --baseline results/baseline.json

# Run login tests only, headed
pytest tests/test_login_performance.py --headed
```

## Test inventory

| Test | File | What it measures |
|---|---|---|
| `test_nav_tab_load` | `tests/test_nav_tab_load.py` | DDT page load for every nav-bar tab: spinner disappearance, table render, TTFB, LCP, CLS, console errors. |
| `test_nav_tab_pagination` | `tests/test_nav_tab_load.py` | Click next-page on each tab and measure table reload time. Skips tabs with a single page. |
| `test_login_page_load` | `tests/test_login_performance.py` | Time from navigation to the Auth0 login form being rendered. |
| `test_login_flow` | `tests/test_login_performance.py` | End-to-end login: page load + credential entry + post-login redirect. Reports page load and login submit times separately. |

## Project structure

```
fordefi-performance/
├── auth/                   # Saved session state (gitignored)
├── configs/
│   ├── pages.py            # Page specs (selectors, capabilities)
│   └── thresholds.py       # Regression thresholds
├── core/
│   ├── benchmark.py        # Baseline comparator
│   ├── console_capture.py  # Browser console message capture
│   ├── evidence.py         # Screenshots & artifact collection
│   ├── logger.py           # Centralized logging factory
│   ├── metrics.py          # AggregatedMetric & MeasurementResult
│   ├── protocols.py        # Protocol interfaces
│   ├── report_writer.py    # JSON/CSV result writer
│   └── timing.py           # perf_counter, Navigation Timing, Web Vitals
├── pages/
│   ├── login_page.py       # Auth0 login page object
│   └── nav_bar_page.py     # Sidebar navigation page object
├── scripts/
│   └── save_auth_state.py  # Manual auth state generator
├── tests/
│   ├── test_login_performance.py
│   └── test_nav_tab_load.py
├── .env.example
├── conftest.py             # Fixtures, CLI options, auth management
├── pytest.ini
└── requirements.txt
```

## Markers

Defined in `pytest.ini`:

| Marker | Purpose |
|---|---|
| `performance` | Performance tests measuring load times and responsiveness |
| `broad_scan` | Lightweight measurement across all scoped pages |
| `deep_dive` | Repeated multi-iteration measurement on hotspot pages |
| `benchmark` | Compare current results against a previous baseline |
| `smoke` | Quick sanity checks before a full performance run |
| `pagination` | Pagination performance tests (next-page table reload) |

## Artifacts and reports

Each performance run writes to a directory under `reports/` with a local timestamp and a short random salt to avoid collisions when running in parallel (e.g. `reports/2026-03-12_18-10-34_a1b2c3d4/`). These directories are gitignored (except `.gitkeep` files).

### Run directory layout

| Path | Description |
|------|--------------|
| `reports/<run>/json/results.json` | Full results: per (page, action) metrics, network summary, screenshot/trace paths. |
| `reports/<run>/json/detailed_metrics_report.json` | Metrics-only report: run_config (iterations, warmup) and per (page, action) full metrics block. |
| `reports/<run>/detailed_metrics_report.html` | Same metrics as HTML with short explanations of what each metric measures. |
| `reports/<run>/csv/results.csv` | Flattened CSV of key metrics per run. |
| `reports/<run>/performance_investigation_report.html` | Main HTML report (summary, deep-dive, network, artifacts). |
| `reports/<run>/screenshots/` | One screenshot per flow (from last iteration when using `--iterations`). |
| `reports/<run>/har/` | HAR file(s) for network evidence. |
| `reports/<run>/traces/` | Playwright traces (when enabled). |

When using `--iterations` > 1, each flow is run multiple times (after discarding `--warmup` runs). Results are aggregated: one row per (page, action) with statistics over the measured samples (median, P95, P99, std dev). The detailed metrics report files reflect these aggregated statistics.

### What each metric measures

**Metrics (per action):**

| Metric | Description |
|--------|-------------|
| **wall_clock** | Total time for the measured action (e.g. navigation or click), from test start to finish (ms). |
| **ttfb** | Time to First Byte: time until the first byte of the response is received from the server (ms). |
| **dom_content_loaded** | When the HTML has been fully loaded and parsed; DOM is ready, scripts may still run (ms). |
| **dom_interactive** | When the document has finished loading and the DOM is ready for user interaction (ms). |
| **load_event_end** | When the load event has finished and all resources have loaded (ms). |
| **lcp** | Largest Contentful Paint: when the largest visible content element is rendered; Core Web Vital (ms). |
| **cls** | Cumulative Layout Shift: measure of visual stability (unwanted layout jumps); lower is better; Core Web Vital (unitless). |

**Statistics columns (per metric):**  
Each metric row in the detailed report tables reports these statistics across the measured runs:

| Column | Description |
|--------|-------------|
| **sample_count** | Number of runs included (after warm-up). Higher counts give more reliable percentiles. |
| **median_ms** | 50th percentile: half of the samples were faster, half slower. Robust to outliers. |
| **p95_ms** | 95th percentile: 95% of runs were at or below this value. Reflects typical worst-case experience. |
| **p99_ms** | 99th percentile: 99% of runs were at or below this value. Captures rare slow runs. |
| **std_dev_ms** | Standard deviation (ms). Low std dev means consistent timings; high means high variance. |
| **min_ms** | Fastest run (ms). |
| **max_ms** | Slowest run (ms). |

*In-page actions* (sort, search, pagination, table_render) only record **wall_clock** (and optional network). TTFB, LCP, and other navigation timings apply to full page loads (e.g. nav_tab_load), not to in-page interactions.
