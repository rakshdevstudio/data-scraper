"""
Timeout utilities for production-grade scraper.
Provides timeout decorators and context managers to prevent indefinite hangs.
"""

import signal
import threading
import functools
from contextlib import contextmanager
from typing import Optional, Callable, Any


class TimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""

    pass


def timeout_guard(seconds: int, error_message: str = "Operation timed out"):
    """
    Decorator to enforce timeout on a function.

    Uses signal.alarm on Unix systems, thread-based timeout on Windows.

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
            # Try signal-based timeout (Unix only)
            if hasattr(signal, "SIGALRM"):

                def timeout_handler(signum, frame):
                    raise TimeoutError(error_message)

                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)
                try:
                    result = func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
                return result
            else:
                # Fallback: thread-based timeout (Windows)
                result = [None]
                exception = [None]

                def target():
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        exception[0] = e

                thread = threading.Thread(target=target)
                thread.daemon = True
                thread.start()
                thread.join(timeout=seconds)

                if thread.is_alive():
                    # Thread still running = timeout
                    raise TimeoutError(error_message)

                if exception[0]:
                    raise exception[0]

                return result[0]

        return wrapper

    return decorator


@contextmanager
def with_timeout(seconds: int, error_message: str = "Operation timed out"):
    """
    Context manager to enforce timeout on a code block.

    Uses signal.alarm on Unix systems, raises TimeoutError on timeout.
    Note: Thread-based fallback not available for context managers.

    Args:
        seconds: Maximum execution time in seconds
        error_message: Custom error message for timeout

    Usage:
        with with_timeout(20, "Business extraction timed out"):
            # ... long running operation
            extract_business_details(url)
    """
    if not hasattr(signal, "SIGALRM"):
        # On Windows, context manager timeout not supported
        # Just yield and hope for the best (individual operations should have timeouts)
        yield
        return

    def timeout_handler(signum, frame):
        raise TimeoutError(error_message)

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def safe_timeout_wrapper(
    func: Callable,
    timeout_seconds: int,
    default_return: Any = None,
    logger: Optional[Callable] = None,
) -> Any:
    """
    Safely execute a function with timeout, returning default on timeout.

    Args:
        func: Function to execute
        timeout_seconds: Maximum execution time
        default_return: Value to return on timeout
        logger: Optional logging function

    Returns:
        Function result or default_return on timeout
    """
    try:

        @timeout_guard(
            timeout_seconds, f"{func.__name__} timed out after {timeout_seconds}s"
        )
        def wrapped():
            return func()

        return wrapped()
    except TimeoutError as e:
        if logger:
            logger(f"TIMEOUT: {str(e)}", level="WARNING")
        return default_return
    except Exception as e:
        if logger:
            logger(f"ERROR in {func.__name__}: {str(e)}", level="ERROR")
        return default_return
