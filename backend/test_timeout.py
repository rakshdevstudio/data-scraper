import time
import logging
from app.timeout_utils import timeout_guard, TimeoutError, safe_timeout_wrapper

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_timeouts():
    logger.info("🧪 STARTING TIMEOUT TEST")

    # 1. Test Success
    logger.info("Step 1: Testing successful execution within timeout...")

    @timeout_guard(2, "Should not timeout")
    def fast_function():
        time.sleep(0.5)
        return "Success"

    try:
        result = fast_function()
        assert result == "Success"
        logger.info("✅ Fast function passed")
    except Exception as e:
        logger.error(f"❌ Fast function failed: {e}")
        raise

    # 2. Test Timeout
    logger.info("Step 2: Testing timeout enforcement...")

    @timeout_guard(2, "Operation timed out")
    def slow_function():
        logger.info("   -> Slow function starting (sleeping 5s)...")
        time.sleep(5)
        logger.info("   -> Slow function finished (should be ignored)")
        return "Failed"

    start = time.time()
    try:
        slow_function()
        logger.error("❌ Slow function did NOT timeout!")
        raise AssertionError("Timeout failed")
    except TimeoutError:
        duration = time.time() - start
        logger.info(f"✅ Timeout captured correctly after {duration:.2f}s")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {type(e).__name__}: {e}")
        raise

    # 3. Test Safe Wrapper
    logger.info("Step 3: Testing safe_timeout_wrapper...")

    def slow_task():
        time.sleep(5)
        return "Original"

    # Adapting logger to accept 'level' kwarg without error
    def test_logger(msg, level="INFO"):
        if level == "ERROR":
            logger.error(msg)
        else:
            logger.warning(msg)

    result = safe_timeout_wrapper(
        slow_task, 2, default_return="Default", logger_func=test_logger
    )
    if result == "Default":
        logger.info("✅ safe_timeout_wrapper returned default value")
    else:
        logger.error(f"❌ safe_timeout_wrapper failed, returned: {result}")
        raise AssertionError("Wrapper failed")

    logger.info("✅ ALL TIMEOUT TESTS PASSED")


if __name__ == "__main__":
    test_timeouts()
