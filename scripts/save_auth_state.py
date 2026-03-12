"""
One-time login helper to save authenticated browser state.

Usage:
    python scripts/save_auth_state.py

Reads USERNAME and PASSWORD from .env, logs into Fordefi preprod,
and saves the session to auth/storage_state.json for test reuse.
"""

import logging
import os
import sys

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    base_url = os.getenv("BASE_URL", "https://app.preprod.fordefi.com")
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    if not username or not password:
        logger.error("USERNAME and PASSWORD must be set in .env")
        sys.exit(1)

    os.makedirs("auth", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        page = context.new_page()
        logger.info("Navigating to %s", base_url)
        page.goto(base_url)

        # Import here to avoid circular dependency when running as standalone script
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pages.login_page import LoginPage

        login = LoginPage(page)
        login.login(username, password)

        logger.info("Waiting for post-login navigation")
        page.wait_for_url(f"{base_url}/**", timeout=30_000)

        context.storage_state(path="auth/storage_state.json")
        browser.close()
        logger.info("Auth state saved to auth/storage_state.json")


if __name__ == "__main__":
    main()
