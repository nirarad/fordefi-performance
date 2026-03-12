"""Vault / connected-account detail page object.

Single vault and single connected-account pages share the same
single-vault-info-widget. This page object covers the detail view
after opening an item from the Vaults or Connected Accounts list.
"""

from dataclasses import dataclass

from playwright.sync_api import Page

from core.logger import get_logger
from core.timing import wait_for_selector

logger = get_logger(__name__)


@dataclass(frozen=True)
class VaultPageSelectors:
    """Selectors for the single vault / connected-account detail page."""
    single_vault_info_widget: str = '[data-test-id="single-vault-info-widget-root"]'


class VaultPage:
    """Page object for the single vault or single connected-account detail view."""

    selectors = VaultPageSelectors()

    def __init__(self, page: Page) -> None:
        self.page = page

    def wait_until_ready(self, timeout: int = 60_000) -> float:
        """Wait for the detail widget to be visible.

        Used for both single vault and single connected-account pages.
        Returns elapsed time in milliseconds.
        """
        return wait_for_selector(
            self.page,
            self.selectors.single_vault_info_widget,
            state="visible",
            timeout=timeout,
            label="single-vault-info-widget",
        )
