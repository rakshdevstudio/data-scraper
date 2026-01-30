import asyncio
import logging
from datetime import datetime
from . import models, database, state
from .scraper_engine import scraper_instance
from .state import ScraperStatus

logger = logging.getLogger(__name__)


class ScraperManager:
    """
    Manages the Async ScraperEngine task within the FastAPI event loop.
    Replaces the subprocess-based ProcessManager.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ScraperManager, cls).__new__(cls)
            cls._instance.scraper_task = None
            cls._instance.job_id = 1
        return cls._instance

    def _get_db(self):
        return database.SessionLocal()

    def _update_status(self, status):
        """Update job status in DB"""
        db = self._get_db()
        try:
            job = db.query(models.Job).filter(models.Job.id == self.job_id).first()
            if not job:
                job = models.Job(id=self.job_id)
                db.add(job)
            job.status = status
            db.commit()

            # Update in-memory state as well
            state.state_manager.set_status(status)
        except Exception as e:
            logger.error(f"Failed to update status DB: {e}")
        finally:
            db.close()

    async def start_scraper(self):
        """Start the scraper as a background asyncio Task"""
        if self.scraper_task and not self.scraper_task.done():
            logger.warning("Scraper task already running.")
            return

        logger.info("🚀 Starting Async Scraper Task...")
        self._update_status(models.JobStatus.RUNNING)
        state.state_manager.clear_logs()  # Optional: clear logs on fresh start

        # Reset flags in engine if any
        scraper_instance._stop_event = False

        # Launch Task
        self.scraper_task = asyncio.create_task(self._run_wrapper())

    async def _run_wrapper(self):
        """Wrapper to handle task completion/failure"""
        try:
            await scraper_instance.run()
            logger.info("✅ Scraper Task Completed Successfully")
            self._update_status(models.JobStatus.STOPPED)  # Or IDLE
        except asyncio.CancelledError:
            logger.info("🛑 Scraper Task Cancelled")
            self._update_status(models.JobStatus.STOPPED)
        except Exception as e:
            logger.error(f"🔥 Scraper Task Crashed: {e}")
            self._update_status(models.JobStatus.ERROR)

    async def stop_scraper(self):
        """Stop the scraper task"""
        if self.scraper_task and not self.scraper_task.done():
            logger.info("🛑 Stopping Scraper Task...")
            state.state_manager.set_status(
                ScraperStatus.STOPPED
            )  # Signal loop to break
            self.scraper_task.cancel()
            try:
                await self.scraper_task
            except asyncio.CancelledError:
                pass
            self._update_status(models.JobStatus.STOPPED)

    async def pause_scraper(self):
        state.state_manager.set_status(ScraperStatus.PAUSED)
        self._update_status(models.JobStatus.PAUSED)
        logger.info("⏸️ Scraper Paused")

    async def resume_scraper(self):
        if not self.scraper_task or self.scraper_task.done():
            await self.start_scraper()
        else:
            state.state_manager.set_status(ScraperStatus.RUNNING)
            self._update_status(models.JobStatus.RUNNING)
            logger.info("▶️ Scraper Resumed")


scraper_manager = ScraperManager()
