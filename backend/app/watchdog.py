"""
Watchdog thread for monitoring scraper progress and auto-recovery.
Detects hangs and automatically restarts browser context.
"""

import datetime
import threading
import time
from typing import Callable, Optional


class WatchdogThread:
    """
    Background thread that monitors scraper progress.
    Triggers auto-recovery if no progress detected within timeout period.
    """

    def __init__(
        self,
        check_interval: int = 10,
        timeout_seconds: int = 60,
        recovery_callback: Optional[Callable] = None,
        logger: Optional[Callable] = None,
    ):
        """
        Initialize watchdog thread.

        Args:
            check_interval: How often to check progress (seconds)
            timeout_seconds: Max time without progress before triggering recovery
            recovery_callback: Function to call when recovery is needed
            logger: Logging function
        """
        self.check_interval = check_interval
        self.timeout_seconds = timeout_seconds
        self.recovery_callback = recovery_callback
        self.logger = logger or print

        self.thread = None
        self.stop_event = threading.Event()
        self.enabled = True

    def start(self):
        """Start the watchdog thread."""
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.logger("Watchdog thread started", level="INFO")

    def stop(self):
        """Stop the watchdog thread."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.logger("Watchdog thread stopped", level="INFO")

    def disable(self):
        """Temporarily disable watchdog checks."""
        self.enabled = False

    def enable(self):
        """Re-enable watchdog checks."""
        self.enabled = True

    def _run(self):
        """Main watchdog loop."""
        from .state import state_manager, ScraperStatus

        while not self.stop_event.is_set():
            try:
                # Sleep in small chunks to allow quick shutdown
                for _ in range(self.check_interval):
                    if self.stop_event.is_set():
                        return
                    time.sleep(1)

                # Skip check if disabled or not running
                if not self.enabled:
                    continue

                state = state_manager.get_state()
                if state["status"] not in [
                    ScraperStatus.RUNNING,
                    ScraperStatus.RECOVERING,
                ]:
                    continue

                # Check last progress time
                watchdog_stats = state_manager.get_watchdog_stats()
                last_progress = watchdog_stats.get("last_progress_time")

                if last_progress is None:
                    # No progress recorded yet, skip
                    continue

                time_since_progress = (
                    datetime.datetime.now() - last_progress
                ).total_seconds()

                if time_since_progress > self.timeout_seconds:
                    # HANG DETECTED
                    self.logger(
                        f"⚠️ WATCHDOG: No progress for {int(time_since_progress)}s (timeout: {self.timeout_seconds}s)",
                        level="WARNING",
                    )
                    self.logger(
                        "⚠️ WATCHDOG: Triggering auto-recovery...", level="WARNING"
                    )

                    # Increment restart counter
                    state_manager.increment_watchdog_restarts()

                    # Set status to RECOVERING
                    state_manager.set_status(ScraperStatus.RECOVERING)

                    # Trigger recovery callback
                    if self.recovery_callback:
                        try:
                            self.recovery_callback()
                            self.logger("✓ WATCHDOG: Recovery completed", level="INFO")

                            # Reset progress time
                            state_manager.update_heartbeat()

                            # Return to RUNNING status
                            state_manager.set_status(ScraperStatus.RUNNING)
                        except Exception as e:
                            self.logger(
                                f"✗ WATCHDOG: Recovery failed: {e}", level="ERROR"
                            )
                            state_manager.set_status(ScraperStatus.ERROR)
                    else:
                        self.logger(
                            "✗ WATCHDOG: No recovery callback configured", level="ERROR"
                        )

            except Exception as e:
                self.logger(f"Watchdog error: {e}", level="ERROR")
                time.sleep(5)  # Back off on error
