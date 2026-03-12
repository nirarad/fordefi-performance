"""Table / data-grid page object for list views.

Covers MUI DataGrid tables: wait for rows, pagination, and opening
the first row (e.g. vault or connected-account detail). Tab-specific
config (ready_selector, supports_pagination) comes from configs.tabs.
"""

from dataclasses import dataclass

from playwright.sync_api import Page

from configs.tabs import get_tab_config
from core.logger import get_logger
from core.timing import wait_for_selector

logger = get_logger(__name__)


@dataclass(frozen=True)
class TablePageSelectors:
    """Selectors for table/grid, pagination, search, and sort."""
    data_grid_row: str = ".MuiDataGrid-row"
    next_page_button: str = '[data-test-id="chevron-right-icon"]'
    search_box_root: str = '[data-test-id="search-box-root"]'
    first_sort_button: str = 'button[aria-label="Sort"]'


class TablePage:
    """Page object for list views that use MUI DataGrid (or similar row-based tables)."""

    selectors = TablePageSelectors()

    def __init__(self, page: Page) -> None:
        self.page = page

    def wait_for_table_rows(
        self,
        tab_name: str,
        timeout: int = 60_000,
    ) -> float | None:
        """Wait for table rows to become visible. Returns ms or None if tab has no table."""
        config = get_tab_config(tab_name)
        if not config.supports_table or not config.ready_selector:
            return None
        return wait_for_selector(
            self.page,
            config.ready_selector,
            state="visible",
            timeout=timeout,
            label=f"{tab_name} table rows",
        )

    @property
    def first_row_id(self) -> str | None:
        """Return the data-id of the first visible table row."""
        row = self.page.locator(self.selectors.data_grid_row).first
        return row.get_attribute("data-id") if row.is_visible(timeout=3_000) else None

    def can_paginate_next(self) -> bool:
        """Return True if the next-page button is visible and enabled."""
        btn = self.page.locator(self.selectors.next_page_button).first
        if not btn.is_visible(timeout=5_000):
            return False
        parent = btn.locator("xpath=ancestor::button")
        if parent.count() > 0 and parent.first.is_disabled():
            return False
        return True

    def click_next_page(self) -> None:
        """Click the next-page pagination button."""
        self.page.locator(self.selectors.next_page_button).first.click()

    def wait_for_page_change(
        self,
        tab_name: str,
        prev_row_id: str,
        timeout: int = 60_000,
    ) -> None:
        """Wait until the first table row has a different data-id than prev_row_id."""
        config = get_tab_config(tab_name)
        self.page.locator(
            f'{config.ready_selector}:not([data-id="{prev_row_id}"])',
        ).first.wait_for(state="visible", timeout=timeout)

    def click_first_table_row(self) -> None:
        """Click the first visible table row (e.g. to open vault or connected-account detail)."""
        self.page.locator(self.selectors.data_grid_row).first.click()

    def is_search_visible(self, timeout: int = 5_000) -> bool:
        """Return True if the search box is visible."""
        loc = self.page.locator(self.selectors.search_box_root).first
        return loc.is_visible(timeout=timeout)

    def type_search(self, query: str) -> None:
        """Focus the search box and type the query (clears existing value)."""
        root = self.page.locator(self.selectors.search_box_root).first
        root.wait_for(state="visible", timeout=10_000)
        input_el = root.locator("input").first
        if input_el.count() > 0:
            input_el.fill(query)
        else:
            root.fill(query)

    def wait_for_table_after_search(self, tab_name: str, timeout: int = 60_000) -> float | None:
        """Wait for table rows to be visible after search. Returns ms or None."""
        return wait_for_selector(
            self.page,
            get_tab_config(tab_name).ready_selector,
            state="visible",
            timeout=timeout,
            label=f"{tab_name} table after search",
        )

    def click_sort_button(self, column_index: int = 0) -> None:
        """Click the sort button for the column at the given index (0-based, e.g. 1 = second column)."""
        self.page.locator(self.selectors.first_sort_button).nth(column_index).click()

    def is_sort_visible(self, column_index: int = 0, timeout: int = 5_000) -> bool:
        """Return True if the sort button for the column at the given index is visible."""
        return self.page.locator(self.selectors.first_sort_button).nth(column_index).is_visible(timeout=timeout)

    def wait_for_table_after_sort(self, tab_name: str, timeout: int = 60_000) -> float | None:
        """Wait for table to finish loading after sort. Returns ms or None."""
        config = get_tab_config(tab_name)
        return wait_for_selector(
            self.page,
            config.ready_selector,
            state="visible",
            timeout=timeout,
            label=f"{tab_name} table after sort",
        )
