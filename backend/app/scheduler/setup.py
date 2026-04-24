import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler.jobs import (
    job_alipay_auto_import,
    job_fetch_fund_holdings,
    job_fetch_market_data,
    job_refresh_market_insight,
    job_strategy_check,
    job_webank_auto_import,
    job_weekly_data_completion,
)
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

    # Weekly data completion: Monday 8:00 — fill missing last-week data from previous week
    scheduler.add_job(
        job_weekly_data_completion,
        "cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly_data_completion",
        replace_existing=True,
    )

    # Fund holdings fetch: 1st of each month at 10:00
    scheduler.add_job(
        job_fetch_fund_holdings,
        "cron",
        day=1,
        hour=10,
        minute=0,
        id="fetch_fund_holdings",
        replace_existing=True,
    )

    # Market insight refresh: Monday 8:30
    scheduler.add_job(
        job_refresh_market_insight,
        "cron",
        day_of_week="mon",
        hour=8,
        minute=30,
        id="refresh_market_insight",
        replace_existing=True,
    )

    alipay_enabled = get_config("alipay_auto_import_enabled", "true")
    if alipay_enabled == "true":
        scheduler.add_job(
            job_alipay_auto_import,
            "cron",
            hour=9,
            minute=5,
            id="alipay_auto_import",
            replace_existing=True,
        )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
