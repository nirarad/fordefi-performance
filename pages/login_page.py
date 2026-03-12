"""Login page object for Fordefi Auth0 login flow.

Two-step flow:
  1. Enter email in #username -> click Continue
  2. Enter password in #password -> click Continue
"""

from dataclasses import dataclass

from playwright.sync_api import Page

from core.logger import get_logger

logger = get_logger(__name__)

LOGIN_TIMEOUT = 30_000


@dataclass(frozen=True)
class LoginSelectors:
    email_input: str = "input#username"
    password_input: str = "input#password"
    continue_button: str = "button[name='action'][value='default']"


class LoginPage:

    selectors = LoginSelectors()

    def __init__(self, page: Page) -> None:
        self.page = page

    def login(self, email: str, password: str) -> None:
        email_input = self.page.locator(self.selectors.email_input)
        password_input = self.page.locator(self.selectors.password_input)
        continue_btn = self.page.locator(self.selectors.continue_button)

        logger.info("Entering email: %s", email)
        email_input.wait_for(state="visible", timeout=LOGIN_TIMEOUT)
        email_input.fill(email)

        logger.info("Clicking Continue")
        continue_btn.click()

        logger.info("Entering password")
        password_input.wait_for(state="visible", timeout=LOGIN_TIMEOUT)
        password_input.fill(password)

        logger.info("Submitting login")
        continue_btn.click()

    def is_login_page(self) -> bool:
        """Check if the current page is the Auth0 login page."""
        return self.page.locator(self.selectors.email_input).is_visible(timeout=3_000)
