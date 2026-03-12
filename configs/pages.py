from dataclasses import dataclass, field
from enum import Enum


class TestPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class PageSpec:
    name: str
    path: str
    test_priority: TestPriority
    deep_dive_candidate: bool = False

    supports_table: bool = False
    supports_spinner: bool = False
    supports_progress_bar: bool = False
    supports_search: bool = False
    supports_sort: bool = False
    supports_filter: bool = False
    supports_pagination: bool = False
    supports_sidebar: bool = False

    search_fields: list[str] = field(default_factory=list)
    default_sort_column: str = ""
    default_filter_scenario: str = ""

    ready_selector_testid: str = ""
    table_selector_testid: str = ""
    spinner_selector_testid: str = ""
    progress_bar_selector_testid: str = ""
    search_input_testid: str = ""
    sort_target_testid: str = ""
    filter_trigger_testid: str = ""
    empty_state_testid: str = ""
    row_selector_testid: str = ""
    sidebar_trigger_testid: str = ""
    sidebar_panel_testid: str = ""


# ---------------------------------------------------------------------------
# Page definitions
# ---------------------------------------------------------------------------
# Selectors use data-testid values. If a required testid is unknown, leave it
# empty and request manual input before running tests that depend on it.
# ---------------------------------------------------------------------------

VAULTS_PAGE = PageSpec(
    name="Vaults",
    path="/vaults",
    test_priority=TestPriority.HIGH,
    deep_dive_candidate=True,
    supports_table=True,
    supports_search=True,
    supports_sort=True,
    supports_filter=True,
    supports_pagination=False,
    supports_sidebar=False,
    # TODO: populate after inspecting the live page
    ready_selector_testid="",
    table_selector_testid="",
    row_selector_testid="",
    search_input_testid="",
    sort_target_testid="",
    filter_trigger_testid="",
)

# Registry of all page specs for parametrized test discovery
ALL_PAGES: list[PageSpec] = [
    VAULTS_PAGE,
]
