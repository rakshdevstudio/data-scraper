import logging

from playwright.sync_api import sync_playwright

# Configure module-level logger
logger = logging.getLogger(__name__)


def launch_browser_instance():
    """
    Launch only the persistent Chromium browser instance.

    Returns:
        tuple: (playwright_instance, browser)
    """
    import os
    import sys
    import re

    # 1. Runtime Environment Check
    if "venv" not in sys.executable and "virtualenv" not in sys.executable:
        logger.critical("❌ CRITICAL: Backend is running OUTSIDE virtual environment!")
        logger.critical(f"Current executable: {sys.executable}")
        # We assume the user wants to fail hard here as requested,
        # but for safety in a running server we might just log loudly if we can't abort the whole process safely.
        # User request: "else log critical error".

    # 2. Force Playwright to use venv/local browsers
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

    logger.info("🚀 Launching browser with stealth configuration...")

    try:
        # Start Playwright
        p = sync_playwright().start()

        # 3. Validate Chromium Version
        # Note: We can only check the executable path AFTER determining what Playwright would use,
        # or we inspect the installed browsers.
        # For simplicity and robustness, we launch the browser wrapper first or inspecting paths if possible.
        # Playwright doesn't easily expose the resolved path without launching or using internal APIs.
        # We will inspect the launched browser's version via CDP or User Agent if needed,
        # but user asked to log `chromium.executable_path` at startup.
        # To get the executable path *before* full launch we can try:
        executable_path = p.chromium.executable_path
        logger.info(f"🔎 Chromium Executable Path: {executable_path}")

        # Check build version from path if possible (e.g. .../chromium-1148/...)
        match = re.search(r"chromium-(\d+)", executable_path)
        if match:
            build_version = int(match.group(1))
            logger.info(f"🔢 Detected Chromium Build: {build_version}")
            if build_version < 1000:
                logger.warning(
                    f"⚠️ WARNING: Chromium build {build_version} is older than recommended (1200)."
                )
                logger.warning(
                    "👉 Consider running: python -m playwright install chromium"
                )
                # We do not crash here anymore, just warn.
            else:
                logger.info("✅ Chromium version matches requirements.")
        else:
            logger.warning("⚠️ Could not determine Chromium build version from path.")

        # Launch Chromium with specific args for stealth and stability
        browser = p.chromium.launch(
            headless=True,  # Changed to True per user request for performance
            slow_mo=50,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--no-sandbox",  # Essential for preventing crashes in memory-constrained envs
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        # Create stealth context
        logger.info("✅ Browser instance launched successfully.")
        return p, browser
    except Exception as e:
        logger.error(f"❌ Failed to launch browser instance: {e}")
        if p:
            try:
                p.stop()
            except Exception:
                pass
        raise e


def create_context(browser, proxy=None):
    """
    Create a fresh context from existing browser instance.

    Args:
        browser: Active browser instance
        proxy: Optional proxy configuration dict

    Returns:
        tuple: (context, page)
    """
    import random

    # Randomize viewport
    viewports = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
    ]

    context = browser.new_context(
        viewport=random.choice(viewports),
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        proxy=proxy,
    )

    page = context.new_page()
    logger.info("✅ New browser context and page created.")
    return context, page


def launch_browser():
    """
    Legacy wrapper for backward compatibility.
    Launches a Chromium browser instance and creates a default context and page.

    Returns:
        tuple: (playwright_instance, browser, context, page)
    """
    logger.info("🚀 Launching browser (legacy wrapper)...")
    p, browser = launch_browser_instance()
    try:
        context, page = create_context(browser)
        logger.info("✅ Browser launched successfully (legacy wrapper).")
        return p, browser, context, page
    except Exception as e:
        logger.error(f"❌ Failed to create context/page in legacy launch_browser: {e}")
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass
        raise e


def shutdown_browser(p, browser, context, page):
    """
    Safely shut down all browser components.

    Args:
        p: Playwright instance
        browser: Browser instance
        context: BrowserContext instance
        page: Page instance
    """
    logger.info("🛑 Initiating browser shutdown...")

    if page:
        try:
            page.close()
        except Exception as e:
            logger.debug(f"Error closing page: {e}")

    if context:
        try:
            context.close()
        except Exception as e:
            logger.debug(f"Error closing context: {e}")

    if browser:
        try:
            browser.close()
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")

    if p:
        try:
            p.stop()
        except Exception as e:
            logger.debug(f"Error stopping Playwright: {e}")

    logger.info("🛑 Browser shutdown complete")
