import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional
import time
import logging

logger = logging.getLogger(__name__)


class GoogleSheetsManager:
    """
    Manages Google Sheets connection and operations with retry logic and error handling.
    """

    def __init__(self, credentials_path: str, sheet_name: str = "MapsScraperResults"):
        self.credentials_path = credentials_path
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        self.worksheet = None
        self.is_connected = False
        self._connect()

    def _connect(self):
        """Authenticate and connect to Google Sheets"""
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]

            creds = Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self.client = gspread.authorize(creds)

            # Open or create sheet
            try:
                self.sheet = self.client.open(self.sheet_name)
                logger.info(f"Opened existing sheet: {self.sheet_name}")
            except gspread.SpreadsheetNotFound:
                self.sheet = self.client.create(self.sheet_name)
                logger.info(f"Created new sheet: {self.sheet_name}")

            # Get or create first worksheet
            try:
                self.worksheet = self.sheet.sheet1
            except Exception as e:
                logger.debug(f"Creating new worksheet: {e}")
                self.worksheet = self.sheet.add_worksheet(
                    title="Results", rows=1000, cols=20
                )

            self.is_connected = True
            logger.info("Google Sheets connection established")

        except FileNotFoundError:
            logger.warning(f"Credentials file not found: {self.credentials_path}")
            logger.warning(
                "Google Sheets integration disabled. Using local backup only."
            )
            self.is_connected = False
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            self.is_connected = False

    def append_rows(self, data: List[Dict], retry_count: int = 3) -> bool:
        """
        Append rows to Google Sheets with retry logic and exponential backoff.

        Args:
            data: List of dictionaries to append
            retry_count: Number of retry attempts

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected:
            logger.warning("Google Sheets not connected, skipping append")
            return False

        if not data:
            return True

        for attempt in range(retry_count):
            try:
                # Convert to list of lists
                if isinstance(data[0], dict):
                    # Ensure headers exist
                    headers = list(data[0].keys())
                    existing_headers = self.worksheet.row_values(1)

                    if not existing_headers or existing_headers == [""]:
                        self.worksheet.append_row(headers)
                        logger.info(f"Created headers: {headers}")

                    # Convert dicts to rows
                    rows = [[str(row.get(h, "")) for h in headers] for row in data]
                else:
                    rows = data

                # Batch append
                self.worksheet.append_rows(rows, value_input_option="RAW")
                logger.info(f"Appended {len(rows)} rows to Google Sheets")
                return True

            except gspread.exceptions.APIError as e:
                error_str = str(e)
                if "RATE_LIMIT" in error_str or "Quota exceeded" in error_str:
                    wait_time = (2**attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                    logger.warning(
                        f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{retry_count})"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Google Sheets API error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Error appending to Google Sheets: {e}")
                if attempt == retry_count - 1:
                    return False
                time.sleep(1)

        return False

    def get_sheet_url(self) -> Optional[str]:
        """Get the URL of the Google Sheet"""
        if self.sheet:
            return self.sheet.url
        return None

    def get_row_count(self) -> int:
        """Get total number of rows in the sheet"""
        if not self.is_connected or not self.worksheet:
            return 0
        try:
            return len(self.worksheet.get_all_values())
        except Exception as e:
            logger.debug(f"Failed to get row count: {e}")
            return 0

    def check_connectivity(self) -> bool:
        """Check if Google Sheets is accessible"""
        if not self.is_connected:
            return False
        try:
            # Try to read first row
            self.worksheet.row_values(1)
            return True
        except Exception:
            logger.warning("Google Sheets connectivity check failed")
            return False
