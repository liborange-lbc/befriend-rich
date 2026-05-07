import logging
from datetime import date, datetime, timedelta

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.price import ExchangeRate, FundDailyPrice
from app.models.scheduler import JobRun

logger = logging.getLogger(__name__)

# Job IDs and their expected freshness (in hours)
JOB_FRESHNESS = {
    "fetch_market_data": 2,
    "strategy_check": 24,
    "webank_auto_import": 48,
    "alipay_auto_import": 48,
    "weekly_data_completion": 168,  # 7 days
    "fetch_fund_holdings": 744,    # ~31 days
    "refresh_market_insight": 168,  # 7 days
    "auto_backup": 48,
}


def get_data_source_overview(db: Session) -> list[dict]:
    """Get health status of all scheduled jobs."""
    results = []
    for job_id, max_hours in JOB_FRESHNESS.items():
        last_run = (
            db.query(JobRun)
            .filter(JobRun.job_id == job_id)
            .order_by(desc(JobRun.started_at))
            .first()
        )
        last_success = (
            db.query(JobRun)
            .filter(JobRun.job_id == job_id, JobRun.status == "success")
            .order_by(desc(JobRun.started_at))
            .first()
        )

        if not last_run:
            status = "unknown"
            detail = "从未运行"
        elif last_run.status == "failed":
            status = "error"
            detail = last_run.summary or "上次运行失败"
        elif last_success:
            hours_ago = (datetime.now() - last_success.started_at).total_seconds() / 3600
            if hours_ago > max_hours * 2:
                status = "error"
                detail = f"上次成功距今 {hours_ago:.0f} 小时"
            elif hours_ago > max_hours:
                status = "warning"
                detail = f"上次成功距今 {hours_ago:.0f} 小时"
            else:
                status = "healthy"
                detail = "正常运行"
        else:
            status = "unknown"
            detail = "从未成功运行"

        results.append({
            "job_id": job_id,
            "status": status,
            "detail": detail,
            "last_run_at": last_run.started_at.isoformat() if last_run else None,
            "last_run_status": last_run.status if last_run else None,
            "last_success_at": last_success.started_at.isoformat() if last_success else None,
        })

    return results


def get_fund_coverage(db: Session) -> list[dict]:
    """Check data freshness for each active fund."""
    today = date.today()
    funds = db.query(Fund).filter(Fund.is_active == True).all()  # noqa: E712

    results = []
    for fund in funds:
        latest_price = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund.id)
            .order_by(desc(FundDailyPrice.date))
            .first()
        )
        total_days = (
            db.query(func.count(FundDailyPrice.id))
            .filter(FundDailyPrice.fund_id == fund.id)
            .scalar()
        )

        if latest_price:
            gap_days = (today - latest_price.date).days
            if gap_days <= 3:
                status = "healthy"
            elif gap_days <= 7:
                status = "warning"
            else:
                status = "error"
        else:
            gap_days = None
            status = "error"

        results.append({
            "fund_id": fund.id,
            "fund_code": fund.code,
            "fund_name": fund.name,
            "data_source": fund.data_source,
            "total_records": total_days,
            "latest_date": latest_price.date.isoformat() if latest_price else None,
            "gap_days": gap_days,
            "status": status,
        })

    return sorted(results, key=lambda x: x["status"] != "error")


def repair_fund_coverage(db: Session) -> list[dict]:
    """修复异常基金数据：对 gap_days > 3 的基金回填最近 30 天数据。"""
    from app.services.market_data.fetcher import fetch_prices_for_fund

    today = date.today()
    start = today - timedelta(days=30)
    funds = db.query(Fund).filter(Fund.is_active == True).all()  # noqa: E712
    results = []

    for fund in funds:
        latest_price = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund.id)
            .order_by(desc(FundDailyPrice.date))
            .first()
        )
        gap_days = (today - latest_price.date).days if latest_price else 999

        if gap_days <= 3:
            continue

        try:
            backfill_start = latest_price.date if latest_price else start
            fetch_prices_for_fund(db, fund, backfill_start, today)
            # 重新检查
            new_latest = (
                db.query(FundDailyPrice)
                .filter(FundDailyPrice.fund_id == fund.id)
                .order_by(desc(FundDailyPrice.date))
                .first()
            )
            new_gap = (today - new_latest.date).days if new_latest else None
            results.append({
                "fund_id": fund.id,
                "fund_code": fund.code,
                "fund_name": fund.name,
                "old_gap": gap_days,
                "new_gap": new_gap,
                "status": "repaired" if new_gap is not None and new_gap <= 3 else "still_stale",
            })
            logger.info(f"Repair {fund.code}: gap {gap_days}d → {new_gap}d")
        except Exception as e:
            results.append({
                "fund_id": fund.id,
                "fund_code": fund.code,
                "fund_name": fund.name,
                "old_gap": gap_days,
                "new_gap": None,
                "status": "failed",
                "error": str(e)[:200],
            })
            logger.error(f"Repair {fund.code} failed: {e}")

    return results


def get_job_history(db: Session, limit: int = 50) -> list[dict]:
    """Get recent job execution history across all jobs."""
    runs = (
        db.query(JobRun)
        .order_by(desc(JobRun.started_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "job_id": r.job_id,
            "status": r.status,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_s": (r.finished_at - r.started_at).total_seconds() if r.finished_at else None,
            "summary": r.summary,
        }
        for r in runs
    ]
