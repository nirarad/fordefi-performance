"""Navigation bar page object for Fordefi sidebar navigation.

Provides locators and navigation helpers for the main sidebar menu items.
Each nav item uses a `data-test-id` attribute with the pattern:
    nav-bar-item-link-{path}
"""

from dataclasses import dataclass

from playwright.sync_api import Locator, Page

from core.logger import get_logger

logger = get_logger(__name__)

NAV_TIMEOUT = 15_000


@dataclass(frozen=True)
class TabConfig:
    path: str
    supports_spinner: bool
    spinner_selector: str
    supports_table: bool
    ready_selector: str


TABS: dict[str, TabConfig] = {
    "Vaults": TabConfig(
        path="/vaults",
        supports_spinner=True,
        spinner_selector=".MuiCircularProgress-circleIndeterminate",
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
    ),
    "Connected Accounts": TabConfig(
        path="/connected-accounts",
        supports_spinner=True,
        spinner_selector=".MuiCircularProgress-circleIndeterminate",
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
    ),
    "Assets": TabConfig(
        path="/assets",
        supports_spinner=True,
        spinner_selector=".MuiCircularProgress-circleIndeterminate",
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
    ),
    "Transactions": TabConfig(
        path="/transactions-history",
        supports_spinner=True,
        spinner_selector=".MuiCircularProgress-circleIndeterminate",
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
    ),
    "Allowances": TabConfig(
        path="/allowances",
        supports_spinner=True,
        spinner_selector=".MuiCircularProgress-circleIndeterminate",
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
    ),
    "Address Book": TabConfig(
        path="/address-book",
        supports_spinner=True,
        spinner_selector=".MuiCircularProgress-circleIndeterminate",
        supports_table=True,
        ready_selector=".MuiDataGrid-row",
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

    title_vaults: str = '[data-test-id="title-item-Vaults"]'
    title_connected_accounts: str = '[data-test-id="title-item-Connected Accounts"]'
    title_assets: str = '[data-test-id="title-item-Assets"]'
    title_transactions: str = '[data-test-id="title-item-Transactions"]'
    title_allowances: str = '[data-test-id="title-item-Allowances"]'
    title_address_book: str = '[data-test-id="title-item-Address Book"]'


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

    # -- state checks --------------------------------------------------------

    def is_tab_active(self, tab_name: str) -> bool:
        """Check if a nav tab is currently active by looking for the isActive suffix."""
        config = self.get_tab_config(tab_name)
        active_selector = (
            f'[data-test-id="nav-bar-item-link-{config.path}-isActive"]'
        )
        return self.page.locator(active_selector).is_visible(timeout=3_000)
