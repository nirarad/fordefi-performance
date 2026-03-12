from typing import Protocol, runtime_checkable


@runtime_checkable
class HasTable(Protocol):
    table_selector_testid: str
    row_selector_testid: str


@runtime_checkable
class Searchable(Protocol):
    search_input_testid: str


@runtime_checkable
class Sortable(Protocol):
    sort_target_testid: str


@runtime_checkable
class Paginated(Protocol):
    pass


@runtime_checkable
class HasSidebar(Protocol):
    sidebar_trigger_testid: str
    sidebar_panel_testid: str


@runtime_checkable
class HasSpinner(Protocol):
    spinner_selector_testid: str


@runtime_checkable
class HasProgressBar(Protocol):
    progress_bar_selector_testid: str
