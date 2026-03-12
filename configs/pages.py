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

    ready_selector: str = ""
    table_selector: str = ""
    row_selector: str = ""
    spinner_selector: str = ""
    progress_bar_selector: str = ""
    search_input_selector: str = ""
    sort_target_selector: str = ""
    filter_trigger_selector: str = ""
    empty_state_selector: str = ""
    sidebar_trigger_selector: str = ""
    sidebar_panel_selector: str = ""


# ---------------------------------------------------------------------------
# Page definitions
# ---------------------------------------------------------------------------

VAULTS_PAGE = PageSpec(
    name="Vaults",
    path="/vaults",
    test_priority=TestPriority.HIGH,
    deep_dive_candidate=True,
    supports_table=True,
    supports_spinner=True,
    supports_search=True,
    supports_sort=True,
    supports_filter=True,
    supports_pagination=False,
    supports_sidebar=False,
    ready_selector=".MuiDataGrid-row",
    table_selector=".MuiDataGrid-main",
    row_selector=".MuiDataGrid-row",
    spinner_selector=".MuiCircularProgress-circleIndeterminate",
)

# Registry of all page specs for parametrized test discovery
ALL_PAGES: list[PageSpec] = [
    VAULTS_PAGE,
]
