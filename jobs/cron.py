import logging
from apscheduler.schedulers.background import BackgroundScheduler

from database.supabase_client import supabase_admin
from jobs.crew import run_jobs_crew
from jobs.tools import scrape_shared_pool

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _run_all_users() -> None:
    """
    Two-phase cron:
      Phase 1 — scrape shared job pool (once, for all roles)
      Phase 2 — run matching for every ready user against the pool
    """
    # ── Phase 1: scrape ───────────────────────────────────────────────────────
    logger.info("[jobs_cron] Phase 1 — scraping shared job pool")
    try:
        summary = scrape_shared_pool()
        total = sum(summary.values())
        logger.info(f"[jobs_cron] Phase 1 done — {total} jobs in pool: {summary}")
    except Exception as e:
        logger.error(f"[jobs_cron] Phase 1 failed: {e}", exc_info=True)
        # Don't abort — users can still match against existing DB pool

    # ── Phase 2: match all ready users ───────────────────────────────────────
    try:
        result = supabase_admin.table("profiles").select("id").eq("status", "ready").execute()
        users = result.data or []
        logger.info(f"[jobs_cron] Phase 2 — matching {len(users)} ready users")
    except Exception as e:
        logger.error(f"[jobs_cron] Phase 2 — failed to fetch users: {e}", exc_info=True)
        return

    for user in users:
        user_id = user["id"]
        try:
            run_jobs_crew(user_id=user_id, limit=10, trigger="cron")
        except Exception as e:
            logger.error(f"[jobs_cron] failed for user={user_id}: {e}", exc_info=True)

    logger.info("[jobs_cron] run complete")


def start_jobs_cron() -> None:
    """Register and start the APScheduler job. Call once from main.py on startup."""
    _scheduler.add_job(
        _run_all_users,
        trigger="interval",
        hours=6,
        id="jobs_cron",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("[jobs_cron] scheduler started — runs every 6 hours")
