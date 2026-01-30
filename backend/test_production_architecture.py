import logging
import time
from app.proxy_manager import ProxyManager
from app.memory_monitor import MemoryMonitor
from app import browser_launcher

# Helper for logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestProduction")


def test_components():
    logger.info("🧪 STARTING PRODUCTION ARCHITECTURE TEST")

    # 1. Test Proxy Manager
    logger.info("Step 1: Testing ProxyManager...")
    pm = ProxyManager(["http://user:pass@1.2.3.4:8080"])
    proxy = pm.get_proxy()
    assert proxy["server"] == "http://1.2.3.4:8080"
    assert proxy["username"] == "user"
    assert proxy["password"] == "pass"

    pm_empty = ProxyManager()
    assert pm_empty.get_proxy() is None
    logger.info("✅ ProxyManager Passed")

    # 2. Test Memory Monitor
    logger.info("Step 2: Testing MemoryMonitor...")
    mm = MemoryMonitor(limit_mb=4096)
    stats = mm.get_stats()
    logger.info(f"Memory Stats: {stats}")
    assert mm.check_memory() is True
    logger.info("✅ MemoryMonitor Passed")

    # 3. Test Browser Architecture (Launch Instance -> Create Context -> Close Context -> Shutdown Instance)
    logger.info("Step 3: Testing Browser Context Factory...")

    # Launch Instance
    logger.info("   -> Launching Instance...")
    p, browser = browser_launcher.launch_browser_instance()
    assert browser.is_connected()

    # Create Context 1
    logger.info("   -> Creating Context 1...")
    ctx1, page1 = browser_launcher.create_context(browser)
    page1.goto("about:blank")
    assert len(browser.contexts) == 1
    ctx1.close()
    logger.info("   -> Context 1 Closed")

    # Create Context 2
    logger.info("   -> Creating Context 2...")
    ctx2, page2 = browser_launcher.create_context(browser)
    page2.goto("about:blank")
    assert len(browser.contexts) == 1  # Previous closed
    ctx2.close()
    logger.info("   -> Context 2 Closed")

    # Shutdown Instance
    logger.info("   -> Shutting down instance...")
    browser.close()
    p.stop()
    logger.info("✅ Browser Architecture Passed")

    logger.info("✅ ALL TESTS PASSED")


if __name__ == "__main__":
    test_components()
