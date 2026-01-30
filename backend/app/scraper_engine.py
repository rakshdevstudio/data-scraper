import threading
import time
import subprocess
import random
from datetime import datetime
from playwright.sync_api import sync_playwright
from . import models, database, config
from .logger import scraper_logger
from .state import state_manager, ScraperStatus
from .data_saver import DataSaver
from .browser_config import BrowserConfig
from .timeout_utils import TimeoutError, timeout_guard
from .watchdog import WatchdogThread


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
        self.browser_type = "chromium"  # Track current browser engine
        self.chromium_failures = 0  # Track consecutive Chromium failures

        # Watchdog and heartbeat threads
        self.watchdog = None
        self.heartbeat_thread = None
        self.heartbeat_stop_event = threading.Event()

        # Browser restart tracking
        self.keywords_processed_since_restart = 0

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
        except Exception:
            pass

        # Log to DB for UI
        if self.db_session:
            try:
                log = models.LogEntry(message=message, level=level)
                self.db_session.add(log)
                self.db_session.commit()
            except Exception:
                self.db_session.rollback()

    def _launch_browser_with_fallback(self, playwright_instance):
        """Launch browser with Chromium first, fallback to Firefox if needed."""
        # Try Chromium first
        if self.browser_type == "chromium" and self.chromium_failures < 3:
            success = self._launch_chromium(playwright_instance)
            if success:
                return True
            else:
                self.chromium_failures += 1
                self._log(
                    f"Chromium failure count: {self.chromium_failures}/3",
                    level="WARNING",
                )

                # After 2 failures, try cache repair
                if self.chromium_failures == 2:
                    self._repair_playwright_cache()

                # After 3 failures, switch to Firefox
                if self.chromium_failures >= 3:
                    self._log(
                        "Chromium failed 3 times. Switching to Firefox...",
                        level="WARNING",
                    )
                    self.browser_type = "firefox"
                    return self._launch_firefox(playwright_instance)

                return False

        # Fallback to Firefox
        return self._launch_firefox(playwright_instance)

    def _launch_chromium(self, playwright_instance):
        """Launch Chromium with platform-specific args and stealth mode."""
        try:
            self._log("Attempting Chromium launch (HEADFUL STEALTH MODE)...")
            args = BrowserConfig.get_chromium_args()
            self._log(f"Launch args: {args}")

            # Launch with headful mode and slow_mo for anti-detection
            self.browser = playwright_instance.chromium.launch(
                headless=config.get_value("headless", False),
                slow_mo=config.get_value("slow_mo", 50),
                args=args,
            )

            # Create context with stealth options
            stealth_options = BrowserConfig.get_stealth_context_options()
            self.context = self.browser.new_context(**stealth_options)
            self.page = self.context.new_page()

            # Remove webdriver flag via CDP
            try:
                client = self.context.new_cdp_session(self.page)
                client.send(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    },
                )
            except Exception:
                pass  # CDP not available in all browsers

            self._log("✓ Chromium launched successfully")

            # Navigate to Maps
            self.page.goto("https://www.google.com/maps", timeout=60000)
            self._log("✓ Navigated to Google Maps")
            return True

        except Exception as e:
            self._log(f"✗ Chromium launch failed: {str(e)[:200]}", level="ERROR")
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass
            return False

    def _launch_firefox(self, playwright_instance):
        """Launch Firefox as fallback browser."""
        try:
            self._log("Attempting Firefox launch (fallback)...")
            args = BrowserConfig.get_firefox_args()

            self.browser = playwright_instance.firefox.launch(
                headless=config.get_value("headless", False),
                slow_mo=config.get_value("slow_mo", 50),
                args=args,
            )

            # Create context with stealth options
            stealth_options = BrowserConfig.get_stealth_context_options()
            self.context = self.browser.new_context(**stealth_options)
            self.page = self.context.new_page()
            self._log("✓ Firefox launched successfully")

            # Navigate to Maps
            self.page.goto("https://www.google.com/maps", timeout=60000)
            self._log("✓ Navigated to Google Maps")
            return True

        except Exception as e:
            self._log(f"✗ Firefox launch failed: {str(e)[:200]}", level="ERROR")
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass
            return False

    def _repair_playwright_cache(self):
        """Repair Playwright cache by reinstalling browsers."""
        try:
            self._log("Attempting Playwright cache repair...", level="WARNING")

            # Try to reinstall Chromium
            result = subprocess.run(
                ["playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                self._log("✓ Playwright Chromium reinstalled successfully")
            else:
                self._log(f"Cache repair failed: {result.stderr[:200]}", level="ERROR")

        except Exception as e:
            self._log(f"Cache repair error: {str(e)[:200]}", level="ERROR")

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

            self._log("DEBUG: Initializing Playwright...")

            # Log browser telemetry
            BrowserConfig.log_browser_info(self._log, self.browser_type)

            with sync_playwright() as p:
                self.playwright = p

                # Try launching browser with fallback
                browser_launched = self._launch_browser_with_fallback(p)

                if not browser_launched:
                    raise Exception(
                        "Failed to launch any browser engine (Chromium and Firefox both failed)"
                    )
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                self._log("DEBUG: Maps loaded. Checking consent...")

                # Consent
                try:
                    consent = self.page.locator(
                        'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
                    )
                    if consent.count() > 0:
                        consent.first.click()
                        self.page.wait_for_timeout(2000)
                except Exception:
                    pass
                self._log("DEBUG: Startup complete. Entering loop...")

                # START WATCHDOG THREAD
                self._log("Starting watchdog thread...")
                self.watchdog = WatchdogThread(
                    check_interval=10,
                    timeout_seconds=config.get_value("watchdog_timeout", 60),
                    recovery_callback=self._watchdog_recovery,
                    logger=self._log,
                )
                self.watchdog.start()

                # START HEARTBEAT THREAD
                self._log("Starting heartbeat thread...")
                self.heartbeat_stop_event.clear()
                self.heartbeat_thread = threading.Thread(
                    target=self._heartbeat_loop, daemon=True
                )
                self.heartbeat_thread.start()

                # Initialize heartbeat
                state_manager.update_heartbeat()

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

                        # KEYWORD TIMEOUT GUARD: Wrap with timeout decorator
                        max_keyword_timeout = config.get_value(
                            "max_keyword_timeout", 180
                        )

                        try:

                            @timeout_guard(
                                max_keyword_timeout,
                                f"Keyword '{k}' timed out after {max_keyword_timeout}s",
                            )
                            def process_with_timeout():
                                self._process_single_keyword(k)

                            process_with_timeout()

                            keyword_obj.status = models.KeywordStatus.DONE
                            self._log(f"Keyword '{k}' DONE")

                        except TimeoutError as te:
                            # Keyword exceeded timeout - mark as SKIPPED
                            self._log(f"⚠️ TIMEOUT: {str(te)}", level="WARNING")
                            keyword_obj.status = models.KeywordStatus.SKIPPED
                            self._log(
                                f"Keyword '{k}' SKIPPED (timeout)", level="WARNING"
                            )

                        self.db_session.commit()
                        processed_count += 1
                        self.keywords_processed_since_restart += 1

                        # AUTO BROWSER RESTART every N keywords
                        restart_interval = config.get_value(
                            "browser_restart_interval", 10
                        )
                        if self.keywords_processed_since_restart >= restart_interval:
                            self._log(
                                f"🔄 Auto-restarting browser (processed {self.keywords_processed_since_restart} keywords)"
                            )
                            self._restart_browser()
                            self.keywords_processed_since_restart = 0

                        if state_manager.should_stop():
                            break

                        # SMART THROTTLING: Random delay between keywords with jitter
                        delay_min = config.get_value("delay_between_keywords_min", 5)
                        delay_max = config.get_value("delay_between_keywords_max", 15)
                        base_sleep = random.uniform(delay_min, delay_max)
                        jitter = random.uniform(-0.2, 0.2) * base_sleep  # ±20% jitter
                        sleep_time = max(1, base_sleep + jitter)  # Ensure at least 1s

                        self._log(
                            f"Throttling: sleeping {sleep_time:.1f}s before next keyword..."
                        )

                        # Sleep in chunks to allow stop interruption
                        elapsed = 0
                        while elapsed < sleep_time:
                            if state_manager.should_stop():
                                break
                            time.sleep(0.5)
                            elapsed += 0.5
                            # Update heartbeat during sleep
                            state_manager.update_heartbeat()

                    except TimeoutError:
                        # Already handled above
                        pass
                    except Exception as e:
                        self._log(f"Error processing '{k}': {str(e)}", level="ERROR")
                        keyword_obj.status = models.KeywordStatus.FAILED
                        self.db_session.commit()

                # STOP WATCHDOG AND HEARTBEAT
                self._log("Stopping watchdog and heartbeat threads...")
                if self.watchdog:
                    self.watchdog.stop()
                self.heartbeat_stop_event.set()
                if self.heartbeat_thread:
                    self.heartbeat_thread.join(timeout=2)

            self._log("Scraper Engine Stopped.")
            state_manager.set_status(ScraperStatus.IDLE)

        except Exception as e:
            self._log(f"Scraper Engine Crash: {e}", level="ERROR")
            # CRASH RECOVERY: Flush data before crashing
            if self.data_saver:
                try:
                    self._log("Emergency data flush...")
                    self.data_saver.flush_all()
                except Exception:
                    pass
            state_manager.set_status(ScraperStatus.ERROR)
        finally:
            # Final flush on any exit
            if self.data_saver:
                try:
                    self.data_saver.flush_all()
                except Exception:
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
                self._log(f"Navigating to details: {url[:60]}...")
                details = self._extract_details(url)
                details["Keyword"] = k
                all_data.append(details)

                # INCREMENTAL SAVE: Save to Google Sheets + local backup immediately
                if self.data_saver:
                    self.data_saver.save_business(details)
                    self._log(f"Saved record for {details.get('Name', 'Unknown')}")

                # SMART THROTTLING: Random delay between business pages
                if idx < len(collected_urls) - 1:  # Don't delay after last business
                    delay_min = config.get_value("delay_between_businesses_min", 2)
                    delay_max = config.get_value("delay_between_businesses_max", 6)
                    base_delay = random.uniform(delay_min, delay_max)
                    jitter = random.uniform(-0.2, 0.2) * base_delay  # ±20% jitter
                    delay = max(1, base_delay + jitter)

                    self._log(f"Throttling: {delay:.1f}s before next business...")
                    time.sleep(delay)
                    state_manager.update_heartbeat()

            except Exception as e:
                self._log(f"Error extracting {url}: {e}", level="ERROR")

    def _ensure_browser_active(self):
        """Restarts the browser if it's closed, crashed, or disconnected."""
        try:
            if (
                self.browser
                and self.browser.is_connected()
                and self.page
                and not self.page.is_closed()
            ):
                return
        except Exception:
            pass

        self._log(
            "Browser session lost or disconnected. Restarting...", level="WARNING"
        )
        try:
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass

            # Use the same browser launch logic as initial startup
            if self.browser_type == "chromium":
                success = self._launch_chromium(self.playwright)
                if not success:
                    self.chromium_failures += 1
                    if self.chromium_failures >= 3:
                        self._log(
                            "Switching to Firefox after repeated failures",
                            level="WARNING",
                        )
                        self.browser_type = "firefox"
                        self._launch_firefox(self.playwright)
            else:
                self._launch_firefox(self.playwright)

            # Handle consent if needed
            try:
                consent = self.page.locator(
                    'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
                )
                if consent.count() > 0:
                    consent.first.click()
                    self.page.wait_for_timeout(2000)
            except Exception:
                pass

        except Exception as e:
            self._log(f"Failed to recover browser: {e}", level="ERROR")
            state_manager.set_status(ScraperStatus.ERROR)
            raise e

    def _watchdog_recovery(self):
        """Called by watchdog thread when hang detected. Restarts browser context."""
        try:
            self._log(
                "🔧 WATCHDOG RECOVERY: Restarting browser context...", level="WARNING"
            )

            # Close current browser
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass

            # Relaunch browser
            if self.browser_type == "chromium":
                success = self._launch_chromium(self.playwright)
                if not success:
                    self._launch_firefox(self.playwright)
            else:
                self._launch_firefox(self.playwright)

            # Handle consent
            try:
                consent = self.page.locator(
                    'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
                )
                if consent.count() > 0:
                    consent.first.click()
                    self.page.wait_for_timeout(2000)
            except Exception:
                pass

            self._log("✓ WATCHDOG RECOVERY: Browser restarted successfully")

        except Exception as e:
            self._log(f"✗ WATCHDOG RECOVERY FAILED: {e}", level="ERROR")
            raise

    def _heartbeat_loop(self):
        """Background thread that logs heartbeat and updates progress timestamp."""
        heartbeat_interval = config.get_value("heartbeat_interval", 5)

        while not self.heartbeat_stop_event.is_set():
            try:
                # Update heartbeat timestamp
                state_manager.update_heartbeat()

                # Log heartbeat (optional, can be verbose)
                # self._log("💓 Heartbeat", level="DEBUG")

                # Sleep in small chunks for quick shutdown
                for _ in range(heartbeat_interval):
                    if self.heartbeat_stop_event.is_set():
                        return
                    time.sleep(1)

            except Exception as e:
                self._log(f"Heartbeat error: {e}", level="ERROR")
                time.sleep(5)

    def _restart_browser(self):
        """Gracefully restart browser to prevent memory leaks and detection."""
        try:
            self._log("Restarting browser for memory cleanup...")

            # Close current browser
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass

            # Relaunch with same browser type
            if self.browser_type == "chromium":
                success = self._launch_chromium(self.playwright)
                if not success:
                    # Don't switch to Firefox on restart, just retry
                    self._launch_chromium(self.playwright)
            else:
                self._launch_firefox(self.playwright)

            # Handle consent
            try:
                consent = self.page.locator(
                    'button[aria-label="Accept all"], button:has-text("Accept all"), button:has-text("Accept")'
                )
                if consent.count() > 0:
                    consent.first.click()
                    self.page.wait_for_timeout(2000)
            except Exception:
                pass

            self._log("✓ Browser restarted successfully")

        except Exception as e:
            self._log(f"Browser restart failed: {e}", level="ERROR")
            # Don't raise - continue with existing browser if possible

    def _scroll_to_bottom(self):
        try:
            self._ensure_browser_active()
            self.page.wait_for_selector('div[role="feed"]', timeout=3000)
            feed = self.page.locator('div[role="feed"]')
            feed.evaluate("element => element.scrollTop = element.scrollHeight")
            time.sleep(2)
        except Exception:
            pass

    def _get_business_urls(self):
        try:
            self._ensure_browser_active()
            self.page.wait_for_selector('a[href*="/maps/place/"]', timeout=2000)
            return self.page.locator('a[href*="/maps/place/"]').evaluate_all(
                "els => els.map(e => e.href)"
            )
        except Exception:
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
            self._log(f"DEBUG: Goto {url[:30]}...")
            self.page.goto(url, timeout=30000)
            self._log("DEBUG: Goto complete. Waiting for load state...")
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            self._log("DEBUG: Load state complete. Waiting for h1...")
            try:
                self.page.wait_for_selector("h1", timeout=5000)
            except Exception:
                pass
            self._log("DEBUG: Ready to extract.")

            # Extract Name with timeout
            try:
                if self.page.locator("h1").count() > 0:
                    data["Name"] = self.page.locator("h1").first.inner_text(
                        timeout=3000
                    )
                    self._log(f"DEBUG: Extracted name: {data['Name'][:30]}")
            except Exception as e:
                self._log(f"DEBUG: Name extraction timeout: {e}", level="WARNING")

            # Extract Ratings with timeout
            try:
                rating_loc = self.page.locator('div[role="img"][aria-label*="stars"]')
                if rating_loc.count() > 0:
                    data["Ratings"] = rating_loc.first.get_attribute(
                        "aria-label", timeout=3000
                    )
            except Exception:
                pass

            # Extract Category with timeout
            try:
                cat_btn = self.page.locator('button[jsaction*="category"]').first
                if cat_btn.count() > 0:
                    data["Niche"] = cat_btn.inner_text(timeout=3000)
            except Exception:
                pass

            # Extract Address with timeout
            try:
                addr_btn = self.page.locator('button[data-item-id="address"]')
                if addr_btn.count() > 0:
                    addr_label = addr_btn.get_attribute("aria-label", timeout=3000)
                    if addr_label:
                        data["Address"] = addr_label.replace("Address: ", "")
            except Exception:
                pass

            # Extract Website with timeout
            try:
                web_btn = self.page.locator('a[data-item-id="authority"]')
                if web_btn.count() > 0:
                    data["Website"] = web_btn.get_attribute("href", timeout=3000)
            except Exception:
                pass

            # Extract Phone with timeout
            try:
                phone_btn = self.page.locator('button[data-item-id*="phone"]')
                if phone_btn.count() > 0:
                    phone_label = phone_btn.get_attribute("aria-label", timeout=3000)
                    if phone_label:
                        data["Contact"] = phone_label.replace("Phone: ", "")
            except Exception:
                pass

            # Extract Hours with timeout
            try:
                hours_div = self.page.locator(
                    'div[aria-label*="Hide open hours"], div[aria-label*="Show open hours"]'
                )
                if hours_div.count() > 0:
                    data["Timings"] = hours_div.get_attribute(
                        "aria-label", timeout=3000
                    )
            except Exception:
                pass

        except Exception as e:
            self._log(f"Extraction error {url}: {e}", level="WARNING")
        return data


# Singleton instance
scraper_instance = ScraperEngine()
