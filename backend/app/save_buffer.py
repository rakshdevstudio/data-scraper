from typing import List, Dict
from datetime import datetime
import threading
import queue
import logging

logger = logging.getLogger(__name__)


class SaveBuffer:
    """
    Thread-safe buffer for batching data saves.
    Automatically flushes when batch size is reached.
    """

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
        self.buffer = []
        self.lock = threading.Lock()
        self.total_saved = 0
        self.failed_queue = queue.Queue()
        self.last_flush_time = datetime.utcnow()

    def add(self, row: Dict) -> List[Dict]:
        """
        Add row to buffer, return rows to save if buffer is full.

        Args:
            row: Dictionary containing business data

        Returns:
            List of rows to save (empty if buffer not full)
        """
        with self.lock:
            self.buffer.append(row)

            if len(self.buffer) >= self.batch_size:
                return self.flush()
        return []

    def flush(self) -> List[Dict]:
        """
        Return and clear buffer.

        Returns:
            List of buffered rows
        """
        with self.lock:
            if not self.buffer:
                return []

            rows = self.buffer.copy()
            self.buffer.clear()
            self.last_flush_time = datetime.utcnow()
            logger.info(f"Flushed {len(rows)} rows from buffer")
            return rows

    def add_failed(self, rows: List[Dict]):
        """Add failed rows to retry queue"""
        for row in rows:
            self.failed_queue.put(row)
        logger.warning(f"Added {len(rows)} rows to failed queue")

    def get_failed(self) -> List[Dict]:
        """Get all failed rows from queue"""
        failed = []
        while not self.failed_queue.empty():
            try:
                failed.append(self.failed_queue.get_nowait())
            except queue.Empty:
                break
        return failed

    def get_stats(self) -> Dict:
        """Get buffer statistics"""
        with self.lock:
            return {
                "buffer_size": len(self.buffer),
                "total_saved": self.total_saved,
                "failed_count": self.failed_queue.qsize(),
                "last_flush": self.last_flush_time.isoformat(),
            }

    def increment_saved(self, count: int):
        """Increment total saved counter"""
        with self.lock:
            self.total_saved += count
