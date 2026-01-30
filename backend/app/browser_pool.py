import logging
from playwright.async_api import async_playwright
import asyncio
from . import config

logger = logging.getLogger(__name__)


class AsyncBrowserPool:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AsyncBrowserPool, cls).__new__(cls)
            cls._instance.playwright = None
            cls._instance.browser = None
            cls._instance.context = None
            cls._instance.config_hash = None
        return cls._instance

    async def get_context(self):
        """
        Get or create a browser context (Async).
        Ensures only one browser instance exists.
        """
        async with self._lock:
            # Check if restart needed (config change or closed)
            current_hash = hash(frozenset(config.load_config().items()))
            if self.browser and self.config_hash != current_hash:
                logger.info("Configuration changed, restarting browser...")
                await self.shutdown()

            if not self.browser:
                await self._start_browser()

            if not self.context:
                await self._create_context()

            # Return a new page in the existing context
            # (or we could manage contexts differently, but sticking to existing pattern)
            # The previous pattern returned (context, page).
            # We'll create a new page for the caller.
            page = await self.context.new_page()
            return self.context, page

    async def release_context(self, context, page):
        """
        Clean up page. We keep the browser/context alive for reuse
        unless explicitly shut down or config changes.
        """
        if page:
            try:
                await page.close()
            except Exception as e:
                logger.debug(f"Error closing page: {e}")

    async def _start_browser(self):
        try:
            logger.info("🚀 Starting Async Browser...")
            self.playwright = await async_playwright().start()

            launch_args = {
                "headless": True,  # Strict headless
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            }

            # Proxy Config
            cfg = config.load_config()
            if cfg.get("use_proxies"):
                # (Proxy logic would go here if we were pulling from proxy_manager,
                # for now keeping simple as per previous file)
                pass

            self.browser = await self.playwright.chromium.launch(**launch_args)
            self.config_hash = hash(frozenset(cfg.items()))
            logger.info("✅ Async Browser Started")
        except Exception as e:
            logger.error(f"❌ Failed to start browser: {e}")
            raise e

    async def _create_context(self):
        if not self.browser:
            return

        try:
            # Viewport randomization could normally go here
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
        except Exception as e:
            logger.error(f"❌ Failed to create context: {e}")
            raise e

    async def shutdown(self):
        logger.info("🛑 Shutting down browser pool...")
        if self.context:
            try:
                await self.context.close()
            except:
                pass
            self.context = None

        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
            self.browser = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except:
                pass
            self.playwright = None


browser_pool = AsyncBrowserPool()
