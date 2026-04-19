import logging

from app.database import SessionLocal
from app.services.market_data.exchange_rate import fetch_and_store_all_rates
from app.services.market_data.fetcher import fetch_all_active_funds
from app.services.strategy.evaluator import run_strategy_check

logger = logging.getLogger(__name__)


def job_fetch_market_data():
    logger.info("Running market data fetch job")
    db = SessionLocal()
    try:
        fetch_all_active_funds(db)
        fetch_and_store_all_rates(db)
    except Exception as e:
        logger.error(f"Market data fetch job failed: {e}")
    finally:
        db.close()


def job_strategy_check():
    logger.info("Running strategy check job")
    db = SessionLocal()
    try:
        run_strategy_check(db)
    except Exception as e:
        logger.error(f"Strategy check job failed: {e}")
    finally:
        db.close()


def job_webank_auto_import():
    """每天 9:00 自动从邮箱拉取微众银行对账单"""
    logger.info("Running WeBank auto import job")
    db = SessionLocal()
    try:
        from app.services.webank.email_puller import pull_latest_statement

        result = pull_latest_statement(db)
        logger.info(f"WeBank auto import completed: {result}")
    except Exception as e:
        logger.error(f"WeBank auto import failed: {e}")
    finally:
        db.close()
