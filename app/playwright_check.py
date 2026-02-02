"""Playwright browser check module.

Verifies that Playwright and Chromium browser are properly installed
and working before server startup.
"""

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


class PlaywrightCheckError(Exception):
    """Error raised when Playwright check fails."""

    pass


async def check_playwright_installation() -> tuple[bool, str]:
    """
    Check if Playwright is installed and Chromium browser is available.

    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        return False, f"Playwright not installed: {e}\nRun: pip install playwright"

    playwright = None
    browser = None
    try:
        playwright = await async_playwright().start()

        # Try to launch Chromium
        browser = await playwright.chromium.launch(headless=True)

        # Create a test page and verify it works
        page = await browser.new_page()
        await page.goto("about:blank")
        title = await page.title()
        await page.close()

        return True, "Playwright and Chromium browser are working correctly"

    except Exception as e:
        error_msg = str(e)

        # Check for common error patterns
        if "Executable doesn't exist" in error_msg or "browserType.launch" in error_msg:
            return False, (
                f"Chromium browser not installed for Playwright.\n"
                f"Run: playwright install chromium\n"
                f"Or for all browsers: playwright install\n"
                f"Error: {error_msg}"
            )
        elif "PLAYWRIGHT_BROWSERS_PATH" in error_msg:
            return False, (
                f"Playwright browser path issue.\n"
                f"Run: playwright install chromium\n"
                f"Error: {error_msg}"
            )
        else:
            return False, f"Playwright check failed: {error_msg}"

    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def check_web_browsing() -> tuple[bool, str]:
    """
    Test that web browsing actually works by fetching a simple page.

    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return False, "Playwright not installed"

    playwright = None
    browser = None
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()

        # Try to navigate to a simple, reliable URL
        # Use example.com as it's specifically designed for testing
        response = await page.goto("https://example.com", timeout=30000)

        if response is None:
            return False, "No response received from test page"

        if response.status != 200:
            return False, f"Test page returned status {response.status}"

        # Verify we got actual content
        title = await page.title()
        if not title:
            return False, "Could not read page title"

        text = await page.inner_text("body")
        if not text or len(text) < 10:
            return False, "Could not read page content"

        await page.close()

        return True, f"Web browsing verified (loaded: example.com, title: {title})"

    except Exception as e:
        error_msg = str(e)
        if "net::ERR_" in error_msg:
            return False, f"Network error - check internet connection: {error_msg}"
        elif "Timeout" in error_msg:
            return False, f"Timeout while loading test page: {error_msg}"
        else:
            return False, f"Web browsing test failed: {error_msg}"

    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def run_startup_checks(skip_web_test: bool = False) -> tuple[bool, list[str]]:
    """
    Run all Playwright startup checks.

    Args:
        skip_web_test: If True, skip the web browsing test (useful for offline mode)

    Returns:
        tuple[bool, list[str]]: (all_passed, list of messages)
    """
    messages = []
    all_passed = True

    # Check 1: Playwright installation
    logger.info("Checking Playwright installation...")
    success, msg = await check_playwright_installation()
    messages.append(f"[{'OK' if success else 'FAIL'}] Playwright: {msg}")
    if not success:
        all_passed = False
        return all_passed, messages

    # Check 2: Web browsing (optional)
    if not skip_web_test:
        logger.info("Checking web browsing capability...")
        success, msg = await check_web_browsing()
        messages.append(f"[{'OK' if success else 'FAIL'}] Web browsing: {msg}")
        if not success:
            all_passed = False
    else:
        messages.append("[SKIP] Web browsing test skipped")

    return all_passed, messages


def check_playwright_sync() -> tuple[bool, list[str]]:
    """
    Synchronous wrapper for startup checks.

    Returns:
        tuple[bool, list[str]]: (all_passed, list of messages)
    """
    return asyncio.run(run_startup_checks())


def require_playwright_or_exit(skip_web_test: bool = False):
    """
    Check Playwright and exit with error if not working.

    This function should be called at server/daemon startup.
    It will print error messages and exit(1) if Playwright is not properly configured.

    Args:
        skip_web_test: If True, skip the web browsing test
    """
    print("\n=== Playwright Browser Check ===")

    try:
        all_passed, messages = asyncio.run(run_startup_checks(skip_web_test))
    except KeyboardInterrupt:
        print("\nCheck cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during Playwright check: {e}")
        print("\nPlease ensure Playwright is installed:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    for msg in messages:
        print(msg)

    if not all_passed:
        print("\n" + "=" * 50)
        print("PLAYWRIGHT CHECK FAILED")
        print("=" * 50)
        print("\nSquidBot requires a working Playwright browser for web browsing.")
        print("\nTo fix this, run the following commands:")
        print("  pip install playwright")
        print("  playwright install chromium")
        print("\nIf you're using Poetry:")
        print("  poetry add playwright")
        print("  poetry run playwright install chromium")
        print("\nServer will not start until browser is properly configured.")
        print("=" * 50 + "\n")
        sys.exit(1)

    print("=== All checks passed ===\n")
    return True


if __name__ == "__main__":
    """Run checks directly for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Check Playwright installation")
    parser.add_argument(
        "--skip-web", action="store_true", help="Skip web browsing test"
    )
    args = parser.parse_args()

    require_playwright_or_exit(skip_web_test=args.skip_web)
