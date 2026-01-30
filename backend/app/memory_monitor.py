import psutil
import os
import logging
import time

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """
    Monitors system and process memory usage to prevent leaks.
    """

    def __init__(self, limit_mb: int = 2048):
        self.limit_mb = limit_mb
        self.process = psutil.Process(os.getpid())

    def check_memory(self) -> bool:
        """
        Check if memory usage is within limits.

        Returns:
            True if within limits, False if exceeded.
        """
        try:
            # RSS (Resident Set Size) is the non-swapped physical memory
            mem_bytes = self.process.memory_info().rss
            mem_mb = mem_bytes / (1024 * 1024)

            if mem_mb > self.limit_mb:
                logger.warning(
                    f"⚠️ Memory limit exceeded: {mem_mb:.1f}MB / {self.limit_mb}MB"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to check memory: {e}")
            return True  # Fail open

    def get_stats(self) -> dict:
        """Get current memory stats."""
        try:
            mem = self.process.memory_info()
            return {
                "rss_mb": mem.rss / (1024 * 1024),
                "vms_mb": mem.vms / (1024 * 1024),
                "percent": self.process.memory_percent(),
            }
        except:
            return {}

    def get_system_memory(self) -> dict:
        """Get system-wide memory status."""
        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "percent": mem.percent,
        }
