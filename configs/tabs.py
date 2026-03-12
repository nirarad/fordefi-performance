"""Tab configuration for nav-bar pages.

Tab paths, capabilities (spinner, table, pagination), and ready selectors
used by NavBarPage and TablePage.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TabConfig:
    path: str
    supports_spinner: bool
    supports_table: bool
    ready_selector: str
    supports_pagination: bool = False
    supports_search: bool = False
    supports_sort: bool = False
    spinner_selector: str = ""  # When empty and supports_spinner, caller uses site default.


TABS: dict[str, TabConfig] = {
    "Vaults": TabConfig(
        path="/vaults",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Connected Accounts": TabConfig(
        path="/connected-accounts",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Assets": TabConfig(
        path="/assets",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Transactions": TabConfig(
        path="/transactions-history",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Allowances": TabConfig(
        path="/allowances",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Address Book": TabConfig(
        path="/address-book",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Transaction Policy": TabConfig(
        path="/transaction-policy",
        supports_spinner=False,
        supports_table=True,
        ready_selector='[data-test-id="policies-rule-row-root"]',
    ),
    "AML Policy": TabConfig(
        path="/aml-policy",
        supports_spinner=False,
        supports_table=True,
        ready_selector='[data-test-id="policies-rule-row-root"]',
    ),
    "User Management": TabConfig(
        path="/user-management",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
        supports_search=True,
        supports_sort=True,
    ),
    "Settings": TabConfig(
        path="/settings",
        supports_spinner=True,
        supports_table=False,
        ready_selector='[data-test-id="page-wrapper-overview-title"]',
    ),
}


def get_tab_config(tab_name: str) -> TabConfig:
    """Return the TabConfig for *tab_name* or raise ValueError."""
    config = TABS.get(tab_name)
    if config is None:
        raise ValueError(
            f"Unknown tab '{tab_name}'. "
            f"Valid tabs: {', '.join(TABS)}"
        )
    return config


# Selector to wait for when opening a single item (first row click) from list.
# Used by single-item load test: click first row then wait for this element.
# Transactions: sidebar load is finished when the details accordion body is visible.
SINGLE_ITEM_DETAIL_SELECTORS: dict[str, str] = {
    "Vaults": '[data-test-id="single-vault-info-widget-root"]',
    "Connected Accounts": '[data-test-id="single-vault-info-widget-root"]',
    "Transactions": '[data-test-id="transaction-details-root"] [data-test-id="accordion-details-body"]',
}


def get_single_item_detail_selector(tab_name: str) -> str | None:
    """Return the detail ready selector for single-item load, or None if not supported."""
    return SINGLE_ITEM_DETAIL_SELECTORS.get(tab_name)
