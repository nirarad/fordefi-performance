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
# Page load (Vaults)
pytest tests/test_page_load.py

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
| `--headed` | Run with a visible browser window (Playwright built-in). |
| `--browser chromium\|firefox\|webkit` | Choose browser engine (Playwright built-in, default: `chromium`). |

### Examples

```bash
# Quick headed run, single session
pytest tests/test_page_load.py --headed --single-session

# Benchmark against a previous baseline
pytest --mode benchmark --baseline results/baseline.json

# Run login tests only, headed
pytest tests/test_login_performance.py --headed
```

## Test inventory

| Test | File | What it measures |
|---|---|---|
| `test_vaults_page_load` | `tests/test_page_load.py` | Full Vaults page load: navigation, spinner disappearance, table render, TTFB, LCP, CLS, console errors. |
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
│   └── test_page_load.py
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

## Artifacts

Screenshots and reports are saved under `artifacts/` and `reports/`. These directories are gitignored (except `.gitkeep` files).
