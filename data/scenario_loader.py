"""Load DDT scenarios from CSV files for pytest.mark.parametrize."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from core.logger import get_logger

logger = get_logger(__name__)

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), "scenarios")


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
    csv_path = os.path.join(SCENARIOS_DIR, f"{page_name}.csv")
    if not os.path.exists(csv_path):
        logger.warning("No scenario CSV found at %s", csv_path)
        return []

    scenarios: list[Scenario] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_action = row.get("action", "").strip()
            if not raw_action or raw_action.startswith("#"):
                continue
            scenarios.append(Scenario(
                action=raw_action,
                param_key=row.get("param_key", "").strip(),
                param_value=row.get("param_value", "").strip(),
                expect_results=row.get("expect_results", "true").strip().lower() == "true",
            ))

    logger.info("Loaded %d scenarios from %s", len(scenarios), csv_path)
    return scenarios


def load_scenarios_by_action(
    page_name: str,
    action: str,
) -> list[Scenario]:
    """Load scenarios filtered to a single action type (search, sort, filter)."""
    return [s for s in load_scenarios(page_name) if s.action == action]
