"""Load DDT scenarios from CSV files for pytest.mark.parametrize."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from core.logger import get_logger

logger = get_logger(__name__)

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")


def _csv_path(filename: str) -> str:
    return os.path.join(SCENARIOS_DIR, filename)


def _csv_bool(value: str) -> bool:
    return value.strip().lower() == "true"


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


def load_scenarios(page_name: str) -> list[Scenario]:
    """Load all scenarios for a given page from its CSV file.

    File expected at: data/scenarios/<page_name>.csv
    Lines starting with '#' are treated as comments and skipped.
    """
    path = _csv_path(f"{page_name}.csv")
    if not os.path.exists(path):
        logger.warning("No scenario CSV found at %s", path)
        return []

    scenarios: list[Scenario] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_action = row.get("action", "").strip()
            if not raw_action or raw_action.startswith("#"):
                continue
            scenarios.append(Scenario(
                action=raw_action,
                param_key=row.get("param_key", "").strip(),
                param_value=row.get("param_value", "").strip(),
                expect_results=_csv_bool(row.get("expect_results", "true")),
            ))

    logger.info("Loaded %d scenarios from %s", len(scenarios), path)
    return scenarios


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
    pages.nav_bar_page.TABS / NavBarPage.
    """
    tab_name: str

    @property
    def test_id(self) -> str:
        return self.tab_name


def load_nav_tab_scenarios() -> list[NavTabScenario]:
    """Load nav-bar tab scenarios from data/scenarios/nav_tabs.csv.

    Lines starting with '#' are treated as comments and skipped.
    """
    path = _csv_path("nav_tabs.csv")
    if not os.path.exists(path):
        logger.warning("No nav-tab CSV found at %s", path)
        return []

    scenarios: list[NavTabScenario] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tab_name = row.get("tab_name", "").strip()
            if not tab_name or tab_name.startswith("#"):
                continue
            scenarios.append(NavTabScenario(tab_name=tab_name))

    logger.info("Loaded %d nav-tab scenarios from %s", len(scenarios), path)
    return scenarios
