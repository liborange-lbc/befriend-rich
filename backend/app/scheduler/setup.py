import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler.jobs import (
    job_alipay_auto_import,
    job_alipay1_auto_import,
    job_futu_auto_import,
    job_longbridge_auto_import,
    job_allocation_recalculate,
    job_auto_backup,
    job_fetch_fund_holdings,
    job_fetch_market_data,
    job_guru_holdings_update,
    job_ic_option_fetch,
    job_refresh_market_insight,
    job_strategy_check,
    job_sync_watch_activities,
    job_us_stock_trend_fetch,
    job_webank_auto_import,
    job_weekly_data_completion,
)
from app.services.config_service import get_config

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Shanghai"))


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

    # Weekly data completion: daily 8:00 — fill missing this-week data from previous week
    scheduler.add_job(
        job_weekly_data_completion,
        "cron",
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

    # Auto backup: daily at 2:00
    scheduler.add_job(
        job_auto_backup,
        "cron",
        hour=2,
        minute=0,
        id="auto_backup",
        replace_existing=True,
    )

    # Allocation recalculation: 1st of Jan/Apr/Jul/Oct at 09:00
    scheduler.add_job(
        job_allocation_recalculate,
        "cron",
        month="1,4,7,10",
        day=1,
        hour=9,
        minute=0,
        id="allocation_recalculate",
        replace_existing=True,
    )

    # IC option data: daily 15:30
    scheduler.add_job(
        job_ic_option_fetch,
        "cron",
        hour=15,
        minute=30,
        id="ic_option_fetch",
        replace_existing=True,
    )

    # Guru holdings update: 5th of each month at 10:30
    scheduler.add_job(
        job_guru_holdings_update,
        "cron",
        day=5,
        hour=10,
        minute=30,
        id="guru_holdings_update",
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

    # Alipay-1 auto import: daily 9:15
    alipay1_enabled = get_config("alipay1_auto_import_enabled", "true")
    if alipay1_enabled == "true":
        scheduler.add_job(
            job_alipay1_auto_import,
            "cron",
            hour=9,
            minute=15,
            id="alipay1_auto_import",
            replace_existing=True,
        )

    # Futu position sync: daily 9:20
    futu_enabled = get_config("futu_auto_import_enabled", "false")
    if futu_enabled == "true":
        scheduler.add_job(
            job_futu_auto_import,
            "cron",
            hour=9,
            minute=20,
            id="futu_auto_import",
            replace_existing=True,
        )

    # Longbridge position sync: daily 9:10
    longbridge_enabled = get_config("longbridge_auto_import_enabled", "false")
    if longbridge_enabled == "true":
        scheduler.add_job(
            job_longbridge_auto_import,
            "cron",
            hour=9,
            minute=10,
            id="longbridge_auto_import",
            replace_existing=True,
        )

    # Watch activity sync: daily 6:00
    scheduler.add_job(
        job_sync_watch_activities,
        "cron",
        hour=6,
        minute=0,
        id="sync_watch_activities",
        replace_existing=True,
    )

    # US stock trend: daily 6:30 (after US market close ~5AM Beijing time)
    scheduler.add_job(
        job_us_stock_trend_fetch,
        "cron",
        hour=6,
        minute=30,
        id="us_stock_trend_fetch",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
