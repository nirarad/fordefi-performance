import os
from playwright.sync_api import Page


def take_screenshot(page: Page, name: str) -> None:
    """Save a screenshot to the reports directory."""
    os.makedirs("reports/screenshots", exist_ok=True)
    page.screenshot(path=f"reports/screenshots/{name}.png", full_page=True)


def get_env(key: str, default: str = "") -> str:
    """Retrieve an environment variable with an optional default."""
    return os.getenv(key, default)
