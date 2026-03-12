"""Navigation bar page object for Fordefi sidebar navigation.

Provides locators and navigation helpers for the main sidebar menu items.
Each nav item uses a `data-test-id` attribute with the pattern:
    nav-bar-item-link-{path}
"""

from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from core.logger import get_logger
from core.timing import wait_for_selector

logger = get_logger(__name__)

NAV_TIMEOUT = 30_000

# Site-wide loading indicator; same selector for all tabs that show a spinner.
SPINNER_SELECTOR = ".MuiCircularProgress-circleIndeterminate"


@dataclass(frozen=True)
class TabConfig:
    path: str
    supports_spinner: bool
    supports_table: bool
    ready_selector: str
    supports_pagination: bool = False
    spinner_selector: str = ""  # When empty and supports_spinner, SPINNER_SELECTOR is used.


TABS: dict[str, TabConfig] = {
    "Vaults": TabConfig(
        path="/vaults",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Connected Accounts": TabConfig(
        path="/connected-accounts",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Assets": TabConfig(
        path="/assets",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Transactions": TabConfig(
        path="/transactions-history",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Allowances": TabConfig(
        path="/allowances",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Address Book": TabConfig(
        path="/address-book",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Transaction Policy": TabConfig(
        path="/transaction-policy",
        supports_spinner=False,
        supports_table=False,
        ready_selector='[data-test-id="policies-rule-row-root"]',
    ),
    "AML Policy": TabConfig(
        path="/aml-policy",
        supports_spinner=False,
        supports_table=False,
        ready_selector='[data-test-id="policies-rule-row-root"]',
    ),
    "User Management": TabConfig(
        path="/user-management",
        supports_spinner=True,
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
        supports_pagination=True,
    ),
    "Settings": TabConfig(
        path="/settings",
        supports_spinner=True,
        supports_table=False,
        ready_selector='[data-test-id="page-wrapper-overview-title"]',
    ),
}


@dataclass(frozen=True)
class NavBarSelectors:
    """CSS selectors that match both active and inactive states of each nav link."""
    vaults: str = '[data-test-id="nav-bar-item-link-/vaults"], [data-test-id="nav-bar-item-link-/vaults-isActive"]'
    connected_accounts: str = '[data-test-id="nav-bar-item-link-/connected-accounts"], [data-test-id="nav-bar-item-link-/connected-accounts-isActive"]'
    assets: str = '[data-test-id="nav-bar-item-link-/assets"], [data-test-id="nav-bar-item-link-/assets-isActive"]'
    transactions: str = '[data-test-id="nav-bar-item-link-/transactions-history"], [data-test-id="nav-bar-item-link-/transactions-history-isActive"]'
    allowances: str = '[data-test-id="nav-bar-item-link-/allowances"], [data-test-id="nav-bar-item-link-/allowances-isActive"]'
    address_book: str = '[data-test-id="nav-bar-item-link-/address-book"], [data-test-id="nav-bar-item-link-/address-book-isActive"]'
    transaction_policy: str = '[data-test-id="nav-bar-item-link-/transaction-policy"], [data-test-id="nav-bar-item-link-/transaction-policy-isActive"]'
    aml_policy: str = '[data-test-id="nav-bar-item-link-/aml-policy"], [data-test-id="nav-bar-item-link-/aml-policy-isActive"]'
    user_management: str = '[data-test-id="nav-bar-item-link-/user-management"], [data-test-id="nav-bar-item-link-/user-management-isActive"]'
    settings: str = '[data-test-id="nav-bar-item-link-/settings"], [data-test-id="nav-bar-item-link-/settings-isActive"]'

    title_vaults: str = '[data-test-id="title-item-Vaults"]'
    title_connected_accounts: str = '[data-test-id="title-item-Connected Accounts"]'
    title_assets: str = '[data-test-id="title-item-Assets"]'
    title_transactions: str = '[data-test-id="title-item-Transactions"]'
    title_allowances: str = '[data-test-id="title-item-Allowances"]'
    title_address_book: str = '[data-test-id="title-item-Address Book"]'
    title_transaction_policy: str = '[data-test-id="title-item-Transaction Policy"]'
    title_aml_policy: str = '[data-test-id="title-item-AML Policy"]'
    title_user_management: str = '[data-test-id="title-item-User Management"]'
    title_settings: str = '[data-test-id="title-item-Settings"]'

    next_page_button: str = '[data-test-id="chevron-right-icon"]'


class NavBarPage:

    selectors = NavBarSelectors()

    def __init__(self, page: Page) -> None:
        self.page = page

    # -- tab config lookup ---------------------------------------------------

    @staticmethod
    def get_tab_config(tab_name: str) -> TabConfig:
        """Return the TabConfig for *tab_name* or raise ValueError."""
        config = TABS.get(tab_name)
        if config is None:
            raise ValueError(
                f"Unknown tab '{tab_name}'. "
                f"Valid tabs: {', '.join(TABS)}"
            )
        return config

    @staticmethod
    def nav_bar_selector(path: str) -> str:
        """Build a CSS selector that matches the nav link in both active and inactive states.

        The app toggles the test-id between
        ``nav-bar-item-link-{path}`` (inactive) and
        ``nav-bar-item-link-{path}-isActive`` (active).
        """
        base = f"nav-bar-item-link-{path}"
        return f'[data-test-id="{base}"], [data-test-id="{base}-isActive"]'

    # -- link locators -------------------------------------------------------

    @property
    def vaults_link(self) -> Locator:
        return self.page.locator(self.selectors.vaults)

    @property
    def connected_accounts_link(self) -> Locator:
        return self.page.locator(self.selectors.connected_accounts)

    @property
    def assets_link(self) -> Locator:
        return self.page.locator(self.selectors.assets)

    @property
    def transactions_link(self) -> Locator:
        return self.page.locator(self.selectors.transactions)

    @property
    def allowances_link(self) -> Locator:
        return self.page.locator(self.selectors.allowances)

    @property
    def address_book_link(self) -> Locator:
        return self.page.locator(self.selectors.address_book)

    @property
    def transaction_policy_link(self) -> Locator:
        return self.page.locator(self.selectors.transaction_policy)

    @property
    def aml_policy_link(self) -> Locator:
        return self.page.locator(self.selectors.aml_policy)

    @property
    def user_management_link(self) -> Locator:
        return self.page.locator(self.selectors.user_management)

    @property
    def settings_link(self) -> Locator:
        return self.page.locator(self.selectors.settings)

    # -- navigation helpers --------------------------------------------------

    def navigate_to(self, tab_name: str) -> None:
        """Click the nav-bar link for *tab_name* and wait for the URL."""
        config = self.get_tab_config(tab_name)
        logger.info("Navigating to %s", tab_name)
        self.page.locator(self.nav_bar_selector(config.path)).click()
        self.page.wait_for_url(f"**{config.path}", timeout=NAV_TIMEOUT)

    def navigate_to_vaults(self) -> None:
        self.navigate_to("Vaults")

    def navigate_to_connected_accounts(self) -> None:
        self.navigate_to("Connected Accounts")

    def navigate_to_assets(self) -> None:
        self.navigate_to("Assets")

    def navigate_to_transactions(self) -> None:
        self.navigate_to("Transactions")

    def navigate_to_allowances(self) -> None:
        self.navigate_to("Allowances")

    def navigate_to_address_book(self) -> None:
        self.navigate_to("Address Book")

    def navigate_to_transaction_policy(self) -> None:
        self.navigate_to("Transaction Policy")

    def navigate_to_aml_policy(self) -> None:
        self.navigate_to("AML Policy")

    def navigate_to_user_management(self) -> None:
        self.navigate_to("User Management")

    def navigate_to_settings(self) -> None:
        self.navigate_to("Settings")

    # -- wait helpers --------------------------------------------------------

    def wait_for_spinner_gone(self, tab_name: str, timeout: int = 60_000) -> float | None:
        """Wait for the tab's spinner to disappear. Returns ms or None if no spinner."""
        config = self.get_tab_config(tab_name)
        if not config.supports_spinner:
            return None
        selector = config.spinner_selector or SPINNER_SELECTOR
        return wait_for_selector(
            self.page, selector,
            state="hidden", timeout=timeout,
            label=f"{tab_name} spinner",
        )

    def wait_for_table_rows(self, tab_name: str, timeout: int = 60_000) -> float | None:
        """Wait for table rows to become visible. Returns ms or None if no table."""
        config = self.get_tab_config(tab_name)
        if not config.supports_table or not config.ready_selector:
            return None
        return wait_for_selector(
            self.page, config.ready_selector,
            state="visible", timeout=timeout,
            label=f"{tab_name} table rows",
        )

    # -- state checks --------------------------------------------------------

    def is_tab_active(self, tab_name: str) -> bool:
        """Check if a nav tab is currently active by looking for the isActive suffix."""
        config = self.get_tab_config(tab_name)
        active_selector = (
            f'[data-test-id="nav-bar-item-link-{config.path}-isActive"]'
        )
        return self.page.locator(active_selector).is_visible(timeout=3_000)

    # -- pagination ----------------------------------------------------------

    def can_paginate_next(self) -> bool:
        """Return True if the next-page button is visible and enabled."""
        btn = self.page.locator(self.selectors.next_page_button).first
        if not btn.is_visible(timeout=5_000):
            return False
        parent = btn.locator("xpath=ancestor::button")
        if parent.count() > 0 and parent.first.is_disabled():
            return False
        return True

    @property
    def first_row_id(self) -> str | None:
        """Return the data-id of the first visible table row."""
        row = self.page.locator(".MuiDataGrid-row").first
        return row.get_attribute("data-id") if row.is_visible(timeout=3_000) else None

    def click_next_page(self) -> None:
        """Click the next-page pagination button."""
        self.page.locator(self.selectors.next_page_button).first.click()

    def wait_for_page_change(self, tab_name: str, prev_row_id: str, timeout: int = 60_000) -> None:
        """Wait until the first table row has a different data-id than prev_row_id."""
        config = self.get_tab_config(tab_name)
        self.page.locator(
            f'{config.ready_selector}:not([data-id="{prev_row_id}"])',
        ).first.wait_for(state="visible", timeout=timeout)
