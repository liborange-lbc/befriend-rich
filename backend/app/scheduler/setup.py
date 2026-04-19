import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler.jobs import job_fetch_market_data, job_strategy_check, job_webank_auto_import
from app.services.config_service import get_config

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    scheduler.add_job(
        job_fetch_market_data,
        "cron",
        minute=0,
        id="fetch_market_data",
        replace_existing=True,
    )

    hours = get_config("scheduler_strategy_hours", "9,12,14")
    scheduler.add_job(
        job_strategy_check,
        "cron",
        hour=hours,
        minute=0,
        id="strategy_check",
        replace_existing=True,
    )
    webank_enabled = get_config("webank_auto_import_enabled", "true")
    if webank_enabled == "true":
        scheduler.add_job(
            job_webank_auto_import,
            "cron",
            hour=9,
            minute=0,
            id="webank_auto_import",
            replace_existing=True,
        )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
