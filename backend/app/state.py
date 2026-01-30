import threading
from enum import Enum
from datetime import datetime
import queue


class ScraperStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"  # Transitional state
    RECOVERING = "recovering"  # Watchdog auto-recovery
    ERROR = "error"


class StateManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self._status = ScraperStatus.IDLE
        self._current_keyword = None
        self._processed_count = 0
        self._total_count = 0
        self._start_time = None
        self.log_queue = queue.Queue()

        # Watchdog tracking
        self._last_progress_time = None
        self._watchdog_restart_count = 0

        # Events for thread control
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()  # Set = Running, Clear = Paused
        self.pause_event.set()  # Default to running (not paused)

    def set_status(self, status: ScraperStatus):
        with self._lock:
            self._status = status
            if status == ScraperStatus.RUNNING:
                self.stop_event.clear()
                self.pause_event.set()
                if not self._start_time:
                    self._start_time = datetime.now()
            elif status == ScraperStatus.PAUSED:
                self.pause_event.clear()
            elif status == ScraperStatus.IDLE or status == ScraperStatus.STOPPING:
                self.stop_event.set()
                self.pause_event.set()  # Unblock pause so we can stop

    def get_state(self):
        with self._lock:
            return {
                "status": self._status,
                "current_keyword": self._current_keyword,
                "processed": self._processed_count,
                "uptime": str(datetime.now() - self._start_time)
                if self._start_time and self._status == ScraperStatus.RUNNING
                else "0:00:00",
            }

    def update_progress(self, keyword: str):
        with self._lock:
            self._current_keyword = keyword
            self._processed_count += 1

    def should_stop(self):
        return self.stop_event.is_set()

    def wait_if_paused(self):
        self.pause_event.wait()

    def reset(self):
        with self._lock:
            self._status = ScraperStatus.IDLE
            self._processed_count = 0
            self._start_time = None
            self._last_progress_time = None
            self._watchdog_restart_count = 0
            self.stop_event.clear()
            self.pause_event.set()

    def update_heartbeat(self):
        """Update last progress timestamp (called by heartbeat thread)."""
        with self._lock:
            self._last_progress_time = datetime.now()

    def get_watchdog_stats(self):
        """Get watchdog statistics for monitoring."""
        with self._lock:
            return {
                "last_progress_time": self._last_progress_time,
                "watchdog_restart_count": self._watchdog_restart_count,
            }

    def increment_watchdog_restarts(self):
        """Increment watchdog restart counter."""
        with self._lock:
            self._watchdog_restart_count += 1


state_manager = StateManager()
