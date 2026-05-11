import fcntl
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler

from database.supabase_client import supabase_admin
from jobs.crew import run_jobs_crew
from jobs.tools import scrape_shared_pool

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
_lock_fd = None


def _run_scraper() -> None:
    logger.info("[jobs_cron] scraper starting")
    try:
        summary = scrape_shared_pool()
        total = sum(summary.values())
        logger.info(f"[jobs_cron] scraper done — {total} jobs in pool: {summary}")
    except Exception as e:
        logger.error(f"[jobs_cron] scraper failed: {e}", exc_info=True)


def _run_user_matching() -> None:
    logger.info("[jobs_cron] user matching starting")
    try:
        result = supabase_admin.table("profiles").select("id").eq("status", "ready").execute()
        users = result.data or []
        logger.info(f"[jobs_cron] matching {len(users)} ready users")
    except Exception as e:
        logger.error(f"[jobs_cron] failed to fetch users: {e}", exc_info=True)
        return

    for user in users:
        user_id = user["id"]
        try:
            run_jobs_crew(user_id=user_id, limit=10, trigger="cron")
        except Exception as e:
            logger.error(f"[jobs_cron] failed for user={user_id}: {e}", exc_info=True)

    logger.info("[jobs_cron] user matching complete")


def start_jobs_cron() -> None:
    """Register and start the APScheduler jobs. Call once from main.py on startup."""
    global _lock_fd
    lock_path = "/tmp/dunno_cron.lock"
    try:
        _lock_fd = open(lock_path, "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        logger.info("[jobs_cron] another worker already owns cron — skipping")
        return

    _scheduler.add_job(
        _run_scraper,
        trigger="interval",
        hours=36,
        id="scraper_cron",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        _run_user_matching,
        trigger="interval",
        hours=12,
        id="matching_cron",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("[jobs_cron] scheduler started — scraper every 36h, matching every 12h")
