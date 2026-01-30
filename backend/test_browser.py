from app.browser_launcher import launch_browser, shutdown_browser
import time
import logging

# Configure logging for test
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_browser_lifecycle():
    logger.info("🧪 STARTING BROWSER TEST")

    p = browser = context = page = None

    try:
        # 1. Launch
        logger.info("Step 1: Launching browser...")
        p, browser, context, page = launch_browser()

        # 2. Navigation
        logger.info("Step 2: Navigating to Google...")
        page.goto("https://google.com")
        logger.info("✅ Navigation successful")

        # 3. Wait
        logger.info("Step 3: Waiting 10 seconds...")
        time.sleep(10)

    except Exception as e:
        logger.error(f"❌ TEST FAILED: {e}")
        raise
    finally:
        # 4. Shutdown
        logger.info("Step 4: Shutting down...")
        shutdown_browser(p, browser, context, page)
        logger.info("✅ TEST COMPLETED")


if __name__ == "__main__":
    test_browser_lifecycle()
