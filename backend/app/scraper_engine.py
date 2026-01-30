import asyncio
import random
from datetime import datetime

from . import models, database, config
from .logger import scraper_logger
from .state import state_manager, ScraperStatus
from .data_saver import DataSaver
from .browser_pool import browser_pool


class ScraperEngine:
    """
    Worker engine that performs the scraping logic (ASYNC).
    Managed by ScraperManager. Uses AsyncBrowserPool for resources.
    """

    def __init__(self):
        self.db_session = None
        self.data_saver = None
        self.context = None
        self.page = None  # Only used for search listing
        self._stop_event = None  # Managed by caller or simple boolean flag in loop

    def _log(self, message, level="INFO"):
        if level == "ERROR":
            scraper_logger.error(message)
        else:
            scraper_logger.info(message)
        print(f"[{level}] {message}")
        try:
            entry = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "message": message,
                "level": level,
            }
            # state_manager.log_queue is a SyncQueue, might need wrapper or direct DB
            # For now, we assume state_manager handles this thread-safely or we just push to DB
            state_manager.log_queue.put(entry)
        except:
            pass
        if self.db_session:
            try:
                log = models.LogEntry(message=message, level=level)
                self.db_session.add(log)
                self.db_session.commit()
            except:
                self.db_session.rollback()

    async def run(self):
        """
        Main Async Loop.
        Caller expects this to run until no keywords left or stopped.
        """
        self.db_session = database.SessionLocal()
        # Initialize stop check based on state_manager

        try:
            dataset_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            self.data_saver = DataSaver(dataset_id, batch_size=10)
            self._log(f"📋 Job Started (Async). Dataset: {dataset_id}")
            self._recover_stuck_keywords()
            self._log("Debug: Stuck keywords recovered", level="DEBUG")

            while True:
                # Check status
                if state_manager.get_state()["status"] == ScraperStatus.STOPPED:
                    break

                await self._check_pause()

                # Check DB for next keyword
                # DB Access is sync, so we keep it direct for now (fast enough) or use run_in_executor if blocking
                keyword_obj = self._get_next_keyword()

                if not keyword_obj:
                    self._log("Debug: No pending keywords. Waiting...", level="DEBUG")
                    await asyncio.sleep(2)
                    continue

                # Process
                await self._process_keyword(keyword_obj.text, keyword_obj)

                # Post-process check
                if state_manager.get_state()["status"] == ScraperStatus.STOPPED:
                    break

                self._log("Debug: Throttling...", level="DEBUG")
                await self._throttle_delay()

        except asyncio.CancelledError:
            self._log("🛑 Scraper task cancelled", level="WARNING")
        except Exception as e:
            self._log(f"🔥 Engine Critical Failure: {e}", level="ERROR")
        finally:
            if self.data_saver:
                self.data_saver.flush_all()
            if self.db_session:
                self.db_session.close()

    async def _process_keyword(self, k, keyword_obj):
        state_manager.update_progress(k)
        self._log(f"Processing Keyword: {k}")
        keyword_obj.status = models.KeywordStatus.PROCESSING
        self.db_session.commit()

        try:
            # 1. Get Context (Async)
            self.context, self.page = await browser_pool.get_context()

            # 2. Perform Work
            try:
                # Clear cookies
                try:
                    await self.context.clear_cookies()
                except:
                    pass

                # Navigation
                await self.page.goto("https://www.google.com/maps", timeout=15000)
                await self._handle_consent()

                await self._perform_scraping(k)

                keyword_obj.status = models.KeywordStatus.DONE
                self._log(f"✅ Keyword '{k}' COMPLETED")

            except Exception as e:
                self._log(f"⚠️ Keyword '{k}' incomplete: {e}", level="WARNING")
                keyword_obj.status = models.KeywordStatus.DONE  # Forced completion

        except Exception as e:
            if "THROTTLED" in str(e) or "Unusual traffic" in str(e):
                self._log(f"🛑 Throttling detected: {e}", level="WARNING")
                keyword_obj.status = models.KeywordStatus.THROTTLED
                await asyncio.sleep(10)
            else:
                self._log(f"❌ Critical Context Error: {e}", level="ERROR")
                keyword_obj.status = models.KeywordStatus.FAILED
        finally:
            if keyword_obj.status in [
                models.KeywordStatus.PENDING,
                models.KeywordStatus.PROCESSING,
            ]:
                keyword_obj.status = models.KeywordStatus.FAILED
            self.db_session.commit()

            # Context Cleanup
            if self.context:
                await browser_pool.release_context(self.context, self.page)
            self.context = None
            self.page = None

    async def _perform_scraping(self, k):
        # Search Box
        try:
            await self.page.wait_for_selector("input", timeout=8000)
            sb = self.page.locator("input#searchboxinput")
            if not await sb.is_visible():
                sb = self.page.get_by_role("combobox", name="Search Google Maps")
            if not await sb.is_visible():
                sb = self.page.locator('input[aria-label="Search Google Maps"]')
            if not await sb.is_visible():
                inputs = await self.page.locator("input").all()
                for i in inputs:
                    if await i.is_visible():
                        sb = i
                        break

            await sb.fill(str(k))
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(3000)

            # Throttling Check
            if await self.page.locator('text="Unusual traffic"').count() > 0:
                raise Exception("THROTTLED: Unusual traffic detected")
        except Exception as e:
            raise Exception(f"Search failed: {e}")

        # Collection Loop
        collected_urls = set()
        scroll_attempts = 0
        max_scrolls = 6

        while scroll_attempts < max_scrolls:
            await self._check_pause()

            await self._scroll_to_bottom()
            urls = await self._get_business_urls()
            new_urls = [u for u in urls if u not in collected_urls]
            collected_urls.update(new_urls)
            self._log(f"Collected {len(collected_urls)} URLs")

            if not new_urls and collected_urls:
                break
            if not new_urls and "/maps/place/" in self.page.url:
                collected_urls.add(self.page.url)
                break

            # STRICT CAP: 20
            if len(collected_urls) >= 20:
                self._log(
                    "Debug: Hit max URL cap (20). Stopping collection.", level="DEBUG"
                )
                break

            next_btn = self.page.locator('button[aria-label="Next page"]')
            if await next_btn.is_visible() and await next_btn.is_enabled():
                await next_btn.click()
                await self.page.wait_for_timeout(2000)
            else:
                scroll_attempts += 1
                if not new_urls:
                    break

        # Extraction Loop
        urls_list = list(collected_urls)[:20]

        for idx, url in enumerate(urls_list):
            await self._check_pause()
            detail_page = None
            try:
                # OPEN FRESH PAGE
                detail_page = await self.context.new_page()

                details = await self._extract_detail_info(detail_page, url)
                if details:
                    details["Keyword"] = k
                    if self.data_saver:
                        # DataSaver is sync but thread-safe enough, or we can offload
                        self.data_saver.save_business(details)

                await asyncio.sleep(random.uniform(1, 2))

            except Exception as e:
                self._log(f"Extraction error for {url}: {e}", level="WARNING")
            finally:
                if detail_page:
                    try:
                        await detail_page.close()
                    except:
                        pass

    async def _extract_detail_info(self, page, url):
        self._log(f"🔍 Extracting: {url}", level="DEBUG")
        data = {"Name": "", "Address": "", "Connect": "", "Website": ""}
        try:
            try:
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            except Exception as e:
                self._log(f"   -> Page load timed out (Skipping)", level="WARNING")
                return None

            # 1. Wait for Name Element
            try:
                await page.wait_for_selector(
                    "h1.DUwDvf", state="attached", timeout=4000
                )
            except:
                pass

            # 2. Extract Name
            name = ""
            if await page.locator("h1.DUwDvf").count() > 0:
                name = (await page.locator("h1.DUwDvf").first.inner_text()).strip()
            elif await page.locator("h1").count() > 0:
                name = (await page.locator("h1").first.inner_text()).strip()

            # 3. SHELL PAGE DETECTION
            if not name or name in ["Google Maps", "Maps"]:
                self._log(
                    f"   -> SHELL PAGE DETECTED ('{name}'). SKIPPING.", level="WARNING"
                )
                return None

            data["Name"] = name
            self._log(f"   -> Found Name: {name}", level="DEBUG")

            # 4. Address
            try:
                btn = page.locator('button[data-item-id="address"]')
                if await btn.count() > 0:
                    lbl = await btn.get_attribute("aria-label") or ""
                    data["Address"] = lbl.replace("Address: ", "").strip()
            except:
                pass

            # 5. Website
            try:
                link = page.locator('a[data-item-id="authority"]')
                if await link.count() > 0:
                    data["Website"] = await link.get_attribute("href")
            except:
                pass

            # 6. Phone
            try:
                btn = page.locator('button[data-item-id^="phone:"]')
                if await btn.count() > 0:
                    lbl = await btn.get_attribute("aria-label") or ""
                    data["Connect"] = lbl.replace("Phone: ", "").strip()
            except:
                pass

        except Exception as e:
            self._log(f"   -> Failed details: {e}", level="DEBUG")

        return data

    async def _scroll_to_bottom(self):
        try:
            feed = self.page.locator('div[role="feed"]')
            if await feed.count() > 0:
                await feed.evaluate(
                    "element => element.scrollTop = element.scrollHeight"
                )
                await asyncio.sleep(2)
        except:
            pass

    async def _get_business_urls(self):
        try:
            urls = await self.page.locator("a.hfpxzc").evaluate_all(
                "els => els.map(e => e.href)"
            )
            if not urls:
                urls = await self.page.locator('a[href*="/maps/place/"]').evaluate_all(
                    "els => els.map(e => e.href)"
                )

            return [
                u
                for u in urls
                if "/maps/place/" in u and "/photo/" not in u and "/reviews" not in u
            ]
        except:
            return []

    async def _handle_consent(self):
        try:
            consent = self.page.locator(
                'button[aria-label="Accept all"], button:has-text("Accept all")'
            )
            if await consent.count() > 0:
                await consent.first.click()
        except:
            pass

    def _recover_stuck_keywords(self):
        # Sync DB op, safe in simple context or wrap if strictly needed
        stuck = (
            self.db_session.query(models.Keyword)
            .filter(models.Keyword.status == models.KeywordStatus.PROCESSING)
            .all()
        )
        for k in stuck:
            k.status = models.KeywordStatus.PENDING
        self.db_session.commit()

    def _get_next_keyword(self):
        return (
            self.db_session.query(models.Keyword)
            .filter(models.Keyword.status == models.KeywordStatus.PENDING)
            .first()
        )

    async def _check_pause(self):
        while state_manager.get_state()["status"] == ScraperStatus.PAUSED:
            await asyncio.sleep(1)

    async def _throttle_delay(self):
        await asyncio.sleep(random.uniform(2, 4))
        state_manager.update_heartbeat()


# Singleton Instance (for compatibility, but Main will likely create one)
scraper_instance = ScraperEngine()
