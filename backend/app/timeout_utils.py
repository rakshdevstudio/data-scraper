"""
Timeout utilities for production-grade scraper.
Provides timeout decorators using ThreadPoolExecutor to prevent indefinite hangs.
Replaces unsafe signal-based timeouts.
"""

import functools
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Callable, Any, Optional

# Configure module-level logger
logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""

    pass


def timeout_guard(seconds: int, error_message: str = "Operation timed out"):
    """
    Decorator to enforce timeout on a function using ThreadPoolExecutor.

    SAFE for multi-threaded environments (unlike signal.alarm).

    Args:
        seconds: Maximum execution time in seconds
        error_message: Custom error message for timeout

    Usage:
        @timeout_guard(180, "Keyword processing timed out")
        def process_keyword(keyword):
            # ... long running operation
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            executor = ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(func, *args, **kwargs)
                return future.result(timeout=seconds)
            except FuturesTimeoutError:
                # Thread is still running in background (cannot be killed safely in Python)
                # But we stop waiting and raise error to control flow.
                # Ideally, the wrapped function should check for a 'stopped' flag if possible,
                # but 'daemon' threads in ThreadPoolExecutor aren't really a thing for individual tasks.
                # This meets the requirement of "Continue scraping without crashing".
                raise TimeoutError(error_message)
            except Exception as e:
                # Re-raise any other exception from the thread
                raise e
            finally:
                # Shutdown executor (won't kill running thread immediately but cleans up resources)
                executor.shutdown(wait=False)

        return wrapper

    return decorator


def safe_timeout_wrapper(
    func: Callable,
    timeout_seconds: int,
    default_return: Any = None,
    logger_func: Optional[Callable] = None,
) -> Any:
    """
    Safely execute a function with timeout, returning default on timeout.

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time
        default_return: Value to return on timeout
        logger_func: Optional logging function

    Returns:
        Function result or default_return on timeout
    """
    try:

        @timeout_guard(timeout_seconds, f"{func.__name__} timed out")
        def wrapped():
            return func()

        return wrapped()
    except TimeoutError as e:
        if logger_func:
            logger_func(f"TIMEOUT: {str(e)}", level="WARNING")
        return default_return
    except Exception as e:
        if logger_func:
            logger_func(f"ERROR in {func.__name__}: {str(e)}", level="ERROR")
        return default_return
