import logging
from apscheduler.schedulers.background import BackgroundScheduler

from database.supabase_client import supabase_admin
from jobs.crew import run_jobs_crew

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _run_all_users() -> None:
    """Fetch all ready users and run the jobs crew for each sequentially."""
    try:
        result = supabase_admin.table("profiles").select("id").eq("status", "ready").execute()
        users = result.data or []
        logger.info(f"[jobs_cron] starting run for {len(users)} ready users")

        for user in users:
            user_id = user["id"]
            try:
                run_jobs_crew(user_id=user_id, limit=10, trigger="cron")
            except Exception as e:
                logger.error(f"[jobs_cron] failed for user={user_id}: {e}", exc_info=True)

        logger.info("[jobs_cron] run complete")
    except Exception as e:
        logger.error(f"[jobs_cron] fatal error: {e}", exc_info=True)


def start_jobs_cron() -> None:
    """Register and start the APScheduler job. Call once from main.py on startup."""
    _scheduler.add_job(
        _run_all_users,
        trigger="interval",
        hours=6,
        id="jobs_cron",
        replace_existing=True,
        max_instances=1,  # prevent overlap if a run takes > 6 hours
    )
    _scheduler.start()
    logger.info("[jobs_cron] scheduler started — runs every 6 hours")
