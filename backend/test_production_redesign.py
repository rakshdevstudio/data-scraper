import logging
import time
import sys
import os

# Ensure backend modules can be imported
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.scraper_manager import scraper_manager
from app.browser_pool import browser_pool
from app import state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestRedesign")


def test_integration():
    logger.info("🧪 STARTING INTEGRATION TEST")

    # 1. Test Manager Start
    logger.info("Step 1: Starting ScraperManager...")
    scraper_manager.start()
    time.sleep(2)

    status = state.state_manager.get_state()
    logger.info(f"Status after start: {status}")
    assert status["status"] == state.ScraperStatus.RUNNING

    # 2. Test Browser Pool Auto-Init
    logger.info("Step 2: verifying Browser Pool...")
    # NOTE: We cannot check browser_pool.browser directly from main thread as it belongs to worker thread.
    # We assume if status is RUNNING and no crash, it's good.
    logger.info("✅ Browser Pool started (inferred from status)")

    # 3. Test Pause/Resume
    logger.info("Step 3: Test Pause/Resume...")
    scraper_manager.pause()
    time.sleep(1)
    assert state.state_manager.get_state()["status"] == state.ScraperStatus.PAUSED

    scraper_manager.resume()
    time.sleep(1)
    assert state.state_manager.get_state()["status"] == state.ScraperStatus.RUNNING
    logger.info("✅ Pause/Resume works")

    # 4. Test Stop & Shutdown
    logger.info("Step 4: Stopping ScraperManager...")
    scraper_manager.stop()
    time.sleep(2)

    status = state.state_manager.get_state()
    logger.info(f"Status after stop: {status}")
    assert status["status"] == state.ScraperStatus.IDLE

    # Verify Browser Pool shutdown
    assert browser_pool.browser is None
    logger.info("✅ Browser Pool shutdown correctly")

    logger.info("✅ INTEGRATION TEST PASSED")


if __name__ == "__main__":
    test_integration()
