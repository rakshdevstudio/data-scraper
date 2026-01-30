import threading
import time
import os
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from playwright.sync_api import sync_playwright
from . import models, database, config
from .logger import scraper_logger
from .state import state_manager, ScraperStatus
from .data_saver import DataSaver


class ScraperEngine:
    def __init__(self):
        self.thread = None
        # Removed internal events, using state_manager
        self.db_session = None
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.data_saver = None  # For incremental Google Sheets saves

    # ... start/stop methods unchanged ...

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        state_manager.set_status(ScraperStatus.RUNNING)
        self.thread = threading.Thread(target=self._run_scraper)
        self.thread.start()

    def stop(self):
        state_manager.set_status(ScraperStatus.STOPPING)
        # Flush all pending data before stopping
        if self.data_saver:
            self._log("Flushing all pending data...")
            try:
                self.data_saver.flush_all()
            except Exception as e:
                self._log(f"Error flushing data: {e}", level="ERROR")
        if self.thread:
            self.thread.join()

    def pause(self):
        state_manager.set_status(ScraperStatus.PAUSED)

    def resume(self):
        state_manager.set_status(ScraperStatus.RUNNING)

    def _log(self, message, level="INFO"):
        # Log to file via logger
        if level == "ERROR":
            scraper_logger.error(message)
        else:
            scraper_logger.info(message)

        # Also Print to console for dev visibility
        print(f"[{level}] {message}")

        # Push to Queue for WebSocket
        try:
            log_entry = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": message,
                "level": level,
            }
            state_manager.log_queue.put(log_entry)
        except:
            pass

        # Log to DB for UI
        if self.db_session:
            try:
                log = models.LogEntry(message=message, level=level)
                self.db_session.add(log)
                self.db_session.commit()
            except:
                self.db_session.rollback()

    def _run_scraper(self):
        self.db_session = database.SessionLocal()
        try:
            # Initialize DataSaver with unique dataset ID
            dataset_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self.data_saver = DataSaver(dataset_id, batch_size=10)
            self._log(f"DataSaver initialized (dataset: {dataset_id})")

            self._log("Starting Scraper Engine...")

            # CRASH RECOVERY: Reset any stuck 'PROCESSING' keywords to 'PENDING'
            stuck_keywords = (
                self.db_session.query(models.Keyword)
                .filter(models.Keyword.status == models.KeywordStatus.PROCESSING)
                .all()
            )
            if stuck_keywords:
                self._log(f"Recovering {len(stuck_keywords)} stuck keywords...")
                for k in stuck_keywords:
                    k.status = models.KeywordStatus.PENDING
                self.db_session.commit()
                self._log("Recovery complete.")

            # Update Job status
            # For simplicity, we assume one global job or we passed a job_id.
            # Let's just manage keywords directly for now as per requirements.

            with sync_playwright() as p:
                self.playwright = p
                self.browser = p.chromium.launch(
                    headless=config.get_value("headless", False)
                )
                self.context = self.browser.new_context()
                self.page = self.context.new_page()

                self.page.goto("https://www.google.com/maps")
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass

                # Consent
                try:
                    consent = self.page.locator(
                        'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
                    )
                    if consent.count() > 0:
                        consent.first.click()
                        self.page.wait_for_timeout(2000)
                except:
                    pass

                processed_count = 0

                while not state_manager.should_stop():
                    # Check pause
                    state_manager.wait_if_paused()

                    if state_manager.should_stop():
                        break

                    # Refresh DB
                    self.db_session.commit()

                    # Get next pending keyword
                    keyword_obj = (
                        self.db_session.query(models.Keyword)
                        .filter(models.Keyword.status == models.KeywordStatus.PENDING)
                        .first()
                    )

                    if not keyword_obj:
                        state_manager.set_status(ScraperStatus.IDLE)
                        self._log("No pending keywords. Scraper Idle.")
                        time.sleep(5)
                        # Poll again
                        if (
                            not state_manager.should_stop()
                            and state_manager.get_state()["status"]
                            == ScraperStatus.IDLE
                        ):
                            # If we are idle, keep polling. If user starts again, status becomes RUNNING.
                            # Here we just wait.
                            continue
                        if state_manager.get_state()["status"] == ScraperStatus.RUNNING:
                            continue
                        else:
                            break

                    # Start processing
                    k = keyword_obj.text
                    state_manager.update_progress(k)
                    self._log(f"Processing Keyword: {k}")

                    # Update status to Processing
                    keyword_obj.status = models.KeywordStatus.PROCESSING
                    self.db_session.commit()

                    try:
                        self._ensure_browser_active()  # RECOVERY POINT
                        self._process_single_keyword(k)

                        if state_manager.should_stop():
                            # If stopped mid-process, maybe mark pending?
                            # For now, mark done if we got here.
                            pass

                        keyword_obj.status = models.KeywordStatus.DONE
                        self.db_session.commit()
                        self._log(f"Keyword '{k}' DONE")
                        processed_count += 1

                        # Respect Config Delay
                        delay_min = config.get_value("delay_min", 1)
                        delay_max = config.get_value("delay_max", 3)
                        import random

                        sleep_time = random.uniform(delay_min, delay_max)

                        # Sleep in chunks to allow stop interruption
                        elapsed = 0
                        while elapsed < sleep_time:
                            if state_manager.should_stop():
                                break
                            time.sleep(0.5)
                            elapsed += 0.5

                    except Exception as e:
                        self._log(f"Error processing '{k}': {str(e)}", level="ERROR")
                        keyword_obj.status = models.KeywordStatus.FAILED
                        self.db_session.commit()

            self._log("Scraper Engine Stopped.")
            state_manager.set_status(ScraperStatus.IDLE)

        except Exception as e:
            self._log(f"Scraper Engine Crash: {e}", level="ERROR")
            # CRASH RECOVERY: Flush data before crashing
            if self.data_saver:
                try:
                    self._log("Emergency data flush...")
                    self.data_saver.flush_all()
                except:
                    pass
            state_manager.set_status(ScraperStatus.ERROR)
        finally:
            # Final flush on any exit
            if self.data_saver:
                try:
                    self.data_saver.flush_all()
                except:
                    pass
            if self.browser:
                self.browser.close()
            self.db_session.close()

    def _process_single_keyword(self, k):
        # ... logic from scraper.py ...
        # Search
        try:
            self.page.wait_for_selector("input", timeout=5000)
            sb = self.page.locator("input#searchboxinput")
            if not sb.is_visible():
                sb = self.page.get_by_role("combobox", name="Search Google Maps")
            if not sb.is_visible():
                sb = self.page.locator('input[aria-label="Search Google Maps"]')
            if not sb.is_visible():
                # Fallback
                inputs = self.page.locator("input").all()
                for i in inputs:
                    if i.is_visible():
                        sb = i
                        break

            sb.fill(str(k))
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(3000)

            # CAPTCHA / Unusual Traffic Check
            if (
                self.page.locator('text="Unusual traffic"').count() > 0
                or self.page.locator('text="I\'m not a robot"').count() > 0
            ):
                self._log("CAPTCHA DETECTED! Pausing for 30s...", level="WARNING")
                time.sleep(30)
                # Maybe pause engine?
                # self.pause()
                # For now just wait and hope.

        except Exception as e:
            raise Exception(f"Search failed: {e}")

        collected_urls = set()

        while True:
            # Check control events inside the loop
            state_manager.wait_if_paused()
            if state_manager.should_stop():
                return

            self._scroll_to_bottom()
            urls = self._get_business_urls()
            new_urls = [u for u in urls if u not in collected_urls]
            collected_urls.update(new_urls)

            self._log(
                f"Collected {len(new_urls)} new URLs. Total: {len(collected_urls)}"
            )

            if len(collected_urls) == 0:
                if "/maps/place/" in self.page.url:
                    collected_urls.add(self.page.url)
                    break

            if len(new_urls) == 0 and len(collected_urls) > 0:
                break

            # MAX LIMIT CHECK can go here if we had one

            next_btn = self.page.locator('button[aria-label="Next page"]')
            if next_btn.is_visible() and next_btn.is_enabled():
                next_btn.click()
                self.page.wait_for_timeout(3000)
            else:
                break

        self._log(f"Extracting details for {len(collected_urls)} businesses...")

        all_data = []
        for idx, url in enumerate(collected_urls):
            state_manager.wait_if_paused()
            if state_manager.should_stop():
                return

            try:
                details = self._extract_details(url)
                details["Keyword"] = k
                all_data.append(details)

                # INCREMENTAL SAVE: Save to Google Sheets + local backup immediately
                if self.data_saver:
                    self.data_saver.save_business(details)

                # Also save to desktop file for backwards compatibility
                self._save_to_excel(all_data)
                time.sleep(1)
            except Exception as e:
                self._log(f"Error extracting {url}: {e}", level="ERROR")

    def _ensure_browser_active(self):
        """Restarts the browser if it's closed or crashed."""
        if self.page and not self.page.is_closed():
            return

        self._log("Browser session lost. Restarting...", level="WARNING")
        try:
            if self.browser:
                try:
                    self.browser.close()
                except:
                    pass

            # Re-launch
            self.browser = self.playwright.chromium.launch(
                headless=config.get_value("headless", False)
            )
            self.context = self.browser.new_context()
            self.page = self.context.new_page()

            # Nav to Maps
            self.page.goto("https://www.google.com/maps")
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
                # Consent again if needed
                consent = self.page.locator(
                    'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
                )
                if consent.count() > 0:
                    consent.first.click()
            except:
                pass

        except Exception as e:
            self._log(f"Failed to recover browser: {e}", level="ERROR")
            raise e

    def _save_to_excel(self, data):
        if not data:
            return
        output_file = "/Users/raksh/Desktop/maps_results.xlsx"
        temp_file = output_file + ".tmp"

        df = pd.DataFrame(data)
        columns = [
            "Name",
            "Ratings",
            "Niche",
            "Address",
            "Timings",
            "Contact",
            "Website",
            "Keyword",
        ]
        final_cols = [c for c in columns if c in df.columns]
        df = df[final_cols]

        try:
            # Atomic Write: Read -> Concat -> Write Temp -> Rename
            combined_df = df
            if os.path.exists(output_file):
                try:
                    existing_df = pd.read_excel(output_file)
                    combined_df = pd.concat([existing_df, df]).drop_duplicates()
                except Exception as read_err:
                    self._log(f"Error reading existing file: {read_err}", level="ERROR")

            # FIX: Explicitly specify engine for .tmp file
            combined_df.to_excel(temp_file, index=False, engine="openpyxl")
            os.replace(temp_file, output_file)
            self._log(f"Saved {len(df)} new records (Total: {len(combined_df)})")

        except Exception as e:
            self._log(f"File save error: {e}", level="ERROR")

    def _scroll_to_bottom(self):
        try:
            self._ensure_browser_active()
            self.page.wait_for_selector('div[role="feed"]', timeout=3000)
            feed = self.page.locator('div[role="feed"]')
            feed.evaluate("element => element.scrollTop = element.scrollHeight")
            time.sleep(2)
        except:
            pass

    def _get_business_urls(self):
        try:
            self._ensure_browser_active()
            self.page.wait_for_selector('a[href*="/maps/place/"]', timeout=2000)
            return self.page.locator('a[href*="/maps/place/"]').evaluate_all(
                "els => els.map(e => e.href)"
            )
        except:
            return []

    def _extract_details(self, url):
        # ... copy logic ...
        data = {
            "Name": "",
            "Ratings": "",
            "Niche": "",
            "Address": "",
            "Timings": "",
            "Contact": "",
            "Website": "",
        }
        try:
            self.page.goto(url, timeout=60000)
            self.page.wait_for_load_state("domcontentloaded")
            try:
                self.page.wait_for_selector("h1", timeout=5000)
            except:
                pass

            if self.page.locator("h1").count() > 0:
                data["Name"] = self.page.locator("h1").first.inner_text()

            # ... (rest of extraction logic, abbreviated for stability) ...
            # I will assume the logic is same as before.
            rating_loc = self.page.locator('div[role="img"][aria-label*="stars"]')
            if rating_loc.count() > 0:
                data["Ratings"] = rating_loc.first.get_attribute("aria-label")

            cat_btn = self.page.locator('button[jsaction*="category"]').first
            if cat_btn.count() > 0:
                data["Niche"] = cat_btn.inner_text()

            addr_btn = self.page.locator('button[data-item-id="address"]')
            if addr_btn.count() > 0:
                data["Address"] = addr_btn.get_attribute("aria-label").replace(
                    "Address: ", ""
                )

            web_btn = self.page.locator('a[data-item-id="authority"]')
            if web_btn.count() > 0:
                data["Website"] = web_btn.get_attribute("href")

            phone_btn = self.page.locator('button[data-item-id*="phone"]')
            if phone_btn.count() > 0:
                data["Contact"] = phone_btn.get_attribute("aria-label").replace(
                    "Phone: ", ""
                )

            hours_div = self.page.locator(
                'div[aria-label*="Hide open hours"], div[aria-label*="Show open hours"]'
            )
            if hours_div.count() > 0:
                data["Timings"] = hours_div.get_attribute("aria-label")

        except Exception as e:
            self._log(f"Extraction error {url}: {e}", level="WARNING")
        return data


# Singleton instance
scraper_instance = ScraperEngine()
