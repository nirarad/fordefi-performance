"""Load DDT scenarios from CSV files for pytest.mark.parametrize."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Callable, TypeVar

from core.logger import get_logger

logger = get_logger(__name__)

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")

T = TypeVar("T")


def csv_path(filename: str) -> str:
    """Return the full path for a scenario CSV file under data/scenarios."""
    return os.path.join(SCENARIOS_DIR, filename)


def csv_bool(value: str) -> bool:
    """Parse a CSV cell as boolean; 'true' (case-insensitive) is True."""
    return value.strip().lower() == "true"


def load_csv_by_column(
    filename: str,
    column_key: str,
    scenario_factory: Callable[[str], T],
    *,
    log_label: str = "scenarios",
) -> list[T]:
    """Load scenarios from a CSV with a single key column.

    Reads data/scenarios/<filename>, skips empty rows and lines where the
    column value starts with '#'. Builds one scenario per row via
    scenario_factory(column_value).

    Args:
        filename: CSV file name (e.g. 'nav_tabs.csv').
        column_key: DictReader column name (e.g. 'tab_name').
        scenario_factory: Callable that builds one scenario from the cell value.
        log_label: Label for log messages.

    Returns:
        List of scenarios; empty if the file is missing or has no valid rows.
    """
    path = csv_path(filename)
    if not os.path.exists(path):
        logger.warning("No %s CSV found at %s", log_label, path)
        return []

    scenarios: list[T] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            value = row.get(column_key, "").strip()
            if not value or value.startswith("#"):
                continue
            scenarios.append(scenario_factory(value))

    logger.info("Loaded %d %s from %s", len(scenarios), log_label, path)
    return scenarios


def load_csv(
    filename: str,
    row_mapper: Callable[[dict[str, str]], T],
    *,
    skip_key: str = "action",
    log_label: str = "scenarios",
) -> list[T]:
    """Load scenarios from a CSV with arbitrary columns.

    Reads data/scenarios/<filename>. Skips rows where skip_key is missing,
    empty, or starts with '#'. Builds one scenario per row via
    row_mapper(row_dict).

    Args:
        filename: CSV file name (e.g. 'vaults.csv').
        row_mapper: Callable that builds one scenario from a row dict.
        skip_key: Column used to detect comments/empty rows.
        log_label: Label for log messages.

    Returns:
        List of scenarios; empty if the file is missing or has no valid rows.
    """
    path = csv_path(filename)
    if not os.path.exists(path):
        logger.warning("No %s CSV found at %s", log_label, path)
        return []

    scenarios: list[T] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            value = row.get(skip_key, "").strip()
            if not value or value.startswith("#"):
                continue
            scenarios.append(row_mapper(row))

    logger.info("Loaded %d %s from %s", len(scenarios), log_label, path)
    return scenarios


# ---------------------------------------------------------------------------
# Generic page-action scenarios (search, sort, filter, …)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    action: str
    param_key: str
    param_value: str
    expect_results: bool

    @property
    def test_id(self) -> str:
        return f"{self.action}-{self.param_key}-{self.param_value}"


def _scenario_from_row(row: dict[str, str]) -> Scenario:
    """Build a Scenario from a CSV row dict."""
    return Scenario(
        action=row.get("action", "").strip(),
        param_key=row.get("param_key", "").strip(),
        param_value=row.get("param_value", "").strip(),
        expect_results=csv_bool(row.get("expect_results", "true")),
    )


def load_scenarios(page_name: str) -> list[Scenario]:
    """Load all scenarios for a given page from its CSV file.

    File expected at: data/scenarios/<page_name>.csv
    Lines starting with '#' are treated as comments and skipped.
    """
    return load_csv(
        f"{page_name}.csv",
        _scenario_from_row,
        skip_key="action",
        log_label="scenarios",
    )


def load_scenarios_by_action(
    page_name: str,
    action: str,
) -> list[Scenario]:
    """Load scenarios filtered to a single action type (search, sort, filter)."""
    return [s for s in load_scenarios(page_name) if s.action == action]


# ---------------------------------------------------------------------------
# Nav-tab load scenarios  (data/scenarios/nav_tabs.csv)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NavTabScenario:
    """Pure test-data row — only carries the tab name.

    Page-specific details (path, selectors, capabilities) live in
    configs.tabs and pages.nav_bar_page.NavBarPage / pages.table_page.TablePage.
    """
    tab_name: str

    @property
    def test_id(self) -> str:
        return self.tab_name


def load_nav_tab_scenarios() -> list[NavTabScenario]:
    """Load nav-bar tab scenarios from data/scenarios/nav_tabs.csv.

    Lines starting with '#' are treated as comments and skipped.
    """
    return load_csv_by_column(
        "nav_tabs.csv",
        "tab_name",
        NavTabScenario,
        log_label="nav-tab",
    )


# ---------------------------------------------------------------------------
# Single-item load scenarios  (data/scenarios/single_item_load.csv)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SingleItemLoadScenario:
    """Test data for single vault / single connected-account load.

    From list table, click first row and measure time until detail page is ready.
    """
    tab_name: str

    @property
    def test_id(self) -> str:
        return f"{self.tab_name}_single_item_load"


def load_single_item_load_scenarios() -> list[SingleItemLoadScenario]:
    """Load single-item load scenarios from data/scenarios/single_item_load.csv."""
    return load_csv_by_column(
        "single_item_load.csv",
        "tab_name",
        SingleItemLoadScenario,
        log_label="single-item-load",
    )
