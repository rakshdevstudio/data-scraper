from .google_sheets import GoogleSheetsManager
from .save_buffer import SaveBuffer
import pandas as pd
from datetime import datetime
from typing import Dict, List
import os
import logging

logger = logging.getLogger(__name__)


class DataSaver:
    """
    Manages incremental data saving to Google Sheets and local backup.
    Ensures zero data loss with dual storage and retry logic.
    """

    def __init__(self, dataset_id: str, batch_size: int = 10):
        self.dataset_id = dataset_id
        self.buffer = SaveBuffer(batch_size=batch_size)
        self.sheets_manager = None
        self.backup_file = f"storage/results_{dataset_id}.xlsx"
        self.local_buffer = []

        # Initialize Google Sheets (gracefully handle missing credentials)
        self._init_google_sheets()

        # Ensure storage directory exists
        os.makedirs("storage", exist_ok=True)

        logger.info(f"DataSaver initialized for dataset: {dataset_id}")

    def _init_google_sheets(self):
        """Initialize Google Sheets manager with error handling"""
        try:
            # Determine project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            # Candidate paths for credentials
            candidates = [
                os.path.join(project_root, "credentials", "service_account.json"),
                os.path.join("credentials", "service_account.json"),
                "service_account.json",
            ]

            creds_path = None
            for p in candidates:
                if os.path.exists(p):
                    creds_path = p
                    break

            if creds_path:
                self.sheets_manager = GoogleSheetsManager(
                    creds_path, "MapsScraperResults"
                )
                logger.info("Google Sheets integration enabled")
            else:
                logger.warning(f"Credentials not found. Searched: {candidates}")
                logger.warning("Google Sheets disabled. Using local backup only.")
                self.sheets_manager = None
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}")
            self.sheets_manager = None

    def save_business(self, business_data: Dict):
        """
        Save single business data with incremental batching.

        Args:
            business_data: Dictionary containing scraped business information
        """
        # Add metadata
        business_data["dataset_id"] = self.dataset_id
        business_data["scraped_at"] = datetime.utcnow().isoformat()

        # Add to buffer
        rows_to_save = self.buffer.add(business_data)

        # Save batch if buffer is full
        if rows_to_save:
            self._save_batch(rows_to_save)

    def _save_batch(self, rows: List[Dict]):
        """
        Save batch to Google Sheets and local backup.

        Args:
            rows: List of business data dictionaries
        """
        if not rows:
            return

        logger.info(f"Saving batch of {len(rows)} businesses")

        # Save to Google Sheets
        google_sheets_success = False
        if self.sheets_manager and self.sheets_manager.is_connected:
            try:
                google_sheets_success = self.sheets_manager.append_rows(rows)
                if google_sheets_success:
                    self.buffer.increment_saved(len(rows))
                    logger.info(f"✅ Saved {len(rows)} rows to Google Sheets")
                else:
                    logger.warning("Google Sheets save failed, adding to retry queue")
                    self.buffer.add_failed(rows)
            except Exception as e:
                logger.error(f"Google Sheets save error: {e}")
                self.buffer.add_failed(rows)
        else:
            logger.info("Google Sheets not available, using local backup only")

        # Always save to local backup
        self._save_local_backup(rows)

    def _save_local_backup(self, rows: List[Dict]):
        """
        Append to local Excel file as backup.

        Args:
            rows: List of business data dictionaries
        """
        try:
            df = pd.DataFrame(rows)

            # Append to existing file or create new
            if os.path.exists(self.backup_file):
                existing_df = pd.read_excel(self.backup_file)
                df = pd.concat([existing_df, df], ignore_index=True)

            df.to_excel(self.backup_file, index=False)
            file_size = os.path.getsize(self.backup_file)
            logger.info(
                f"✅ Local backup saved: {self.backup_file} ({file_size} bytes)"
            )

        except Exception as e:
            logger.error(f"❌ Local backup failed: {e}")

    def flush_all(self):
        """
        Flush all pending data (called on stop/pause).
        Ensures zero data loss.
        """
        logger.info("Flushing all pending data...")

        # Flush buffer
        rows = self.buffer.flush()
        if rows:
            self._save_batch(rows)

        # Retry failed saves
        failed = self.buffer.get_failed()
        if failed:
            logger.info(f"Retrying {len(failed)} failed saves")
            self._save_batch(failed)

        logger.info("✅ All data flushed successfully")

    def get_stats(self) -> Dict:
        """Get data saver statistics"""
        stats = self.buffer.get_stats()
        stats["dataset_id"] = self.dataset_id
        stats["backup_file"] = self.backup_file

        if self.sheets_manager:
            stats["google_sheets_url"] = self.sheets_manager.get_sheet_url()
            stats["google_sheets_connected"] = self.sheets_manager.is_connected
            stats["google_sheets_row_count"] = self.sheets_manager.get_row_count()
        else:
            stats["google_sheets_connected"] = False

        # Local backup stats
        if os.path.exists(self.backup_file):
            stats["backup_file_size"] = os.path.getsize(self.backup_file)
            try:
                df = pd.read_excel(self.backup_file)
                stats["backup_row_count"] = len(df)
            except Exception as e:
                logger.warning(f"Could not read backup file for stats: {e}")
                stats["backup_row_count"] = 0
        else:
            stats["backup_file_size"] = 0
            stats["backup_row_count"] = 0

        return stats
