import logging
from datetime import datetime
from functools import wraps

from app.database import SessionLocal
from app.services.market_data.exchange_rate import fetch_and_store_all_rates
from app.services.market_data.fetcher import fetch_all_active_funds
from app.services.strategy.evaluator import run_strategy_check

logger = logging.getLogger(__name__)


def _record_run(job_id: str):
    """Decorator to record job execution in job_runs table."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from app.models.scheduler import JobRun
            db = SessionLocal()
            run = JobRun(job_id=job_id, started_at=datetime.now(), status="running")
            try:
                db.add(run)
                db.commit()
                db.refresh(run)
                result = func(*args, **kwargs)
                run.status = "success"
                run.summary = str(result) if result else "OK"
                run.finished_at = datetime.now()
                db.commit()
                return result
            except Exception as e:
                run.status = "failed"
                run.summary = str(e)[:500]
                run.finished_at = datetime.now()
                db.commit()
                raise
            finally:
                db.close()
        return wrapper
    return decorator


@_record_run("fetch_market_data")
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


@_record_run("strategy_check")
def job_strategy_check():
    logger.info("Running strategy check job")
    db = SessionLocal()
    try:
        run_strategy_check(db)
    except Exception as e:
        logger.error(f"Strategy check job failed: {e}")
    finally:
        db.close()


@_record_run("webank_auto_import")
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


@_record_run("weekly_data_completion")
def job_weekly_data_completion():
    """每周一 8:00 检查上周数据，缺失则用前一周补全。"""
    from datetime import date, timedelta

    from app.models.fund import Fund
    from app.models.portfolio import PortfolioRecord

    logger.info("Running weekly data completion job")
    db = SessionLocal()
    try:
        today = date.today()
        # Last week's Monday
        last_monday = today - timedelta(days=today.weekday() + 7)
        # Two weeks ago Monday
        prev_monday = last_monday - timedelta(days=7)

        # For each (channel, fund_id) that has records in prev_monday but not last_monday, copy
        prev_records = (
            db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == prev_monday)
            .all()
        )
        existing_last_week = set(
            (r.fund_id, r.channel)
            for r in db.query(PortfolioRecord)
            .filter(PortfolioRecord.record_date == last_monday)
            .all()
        )

        filled = 0
        for pr in prev_records:
            if (pr.fund_id, pr.channel) not in existing_last_week:
                db.add(PortfolioRecord(
                    fund_id=pr.fund_id,
                    record_date=last_monday,
                    channel=pr.channel,
                    amount=pr.amount,
                    amount_cny=pr.amount_cny,
                    profit=pr.profit,
                    weekly_investment=None,  # No new investment assumed
                ))
                filled += 1

        if filled:
            db.commit()
            from app.services.portfolio.snapshot import generate_snapshot
            generate_snapshot(db, last_monday)

        logger.info(f"Weekly data completion: filled {filled} records for {last_monday}")
    except Exception as e:
        logger.error(f"Weekly data completion failed: {e}")
    finally:
        db.close()


@_record_run("fetch_fund_holdings")
def job_fetch_fund_holdings():
    """每月1日 10:00 抓取基金持仓数据（检查新的季度披露）"""
    logger.info("Running fund holdings fetch job")
    db = SessionLocal()
    try:
        from app.services.fund_holding_service import fetch_holdings_for_all_funds

        result = fetch_holdings_for_all_funds(db)
        logger.info(f"Fund holdings fetch completed: {result}")
    except Exception as e:
        logger.error(f"Fund holdings fetch failed: {e}")
    finally:
        db.close()


@_record_run("refresh_market_insight")
def job_refresh_market_insight():
    """每周一 8:30 刷新大盘洞察数据"""
    logger.info("Running market insight refresh job")
    db = SessionLocal()
    try:
        from app.services.market_insight.grid import refresh_market_data

        refresh_market_data(db)
    except Exception as e:
        logger.error(f"Market insight refresh failed: {e}")
    finally:
        db.close()


@_record_run("alipay_auto_import")
def job_alipay_auto_import():
    """每天 9:05 自动从邮箱拉取支付宝基金对账单"""
    logger.info("Running Alipay auto import job")
    db = SessionLocal()
    try:
        from app.services.alipay.email_puller import pull_alipay_statements

        result = pull_alipay_statements(db)
        if result:
            logger.info(f"Alipay auto import completed: {result}")
        else:
            logger.info("Alipay auto import: nothing new to import")
    except Exception as e:
        logger.error(f"Alipay auto import failed: {e}")
    finally:
        db.close()
