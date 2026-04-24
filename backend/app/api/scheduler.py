"""Scheduler API — list jobs, view run history, trigger manual runs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.scheduler import JobRun
from app.response import ok
from app.scheduler.setup import scheduler

router = APIRouter()

# Static job metadata (matches job IDs in setup.py)
JOB_META = {
    "fetch_market_data": {
        "name": "基金行情与汇率",
        "description": "抓取所有活跃基金的最新行情数据及汇率",
    },
    "strategy_check": {
        "name": "策略监控",
        "description": "根据用户配置的策略规则检查是否触发条件并发送提醒",
    },
    "webank_auto_import": {
        "name": "微众银行对账单",
        "description": "从163邮箱拉取最新的微众银行资产对账单并自动导入",
    },
    "alipay_auto_import": {
        "name": "支付宝基金对账单",
        "description": "从163邮箱拉取最新的支付宝基金对账单并自动导入",
    },
    "weekly_data_completion": {
        "name": "周数据补全",
        "description": "检查上周是否有缺失的持仓数据，用前一周数据补全",
    },
    "fetch_fund_holdings": {
        "name": "基金持仓抓取",
        "description": "从天天基金抓取所有活跃基金的最新季报持仓数据",
    },
    "refresh_market_insight": {
        "name": "大盘洞察刷新",
        "description": "刷新A股市值快照、指数成分股及行业分类数据",
    },
}


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    """List all scheduled jobs with metadata, schedule, next run, and latest run."""
    jobs = scheduler.get_jobs()
    result = []
    for job in jobs:
        meta = JOB_META.get(job.id, {})
        # Get trigger description
        trigger_str = str(job.trigger) if job.trigger else ""
        next_run = str(job.next_run_time) if job.next_run_time else None

        # Latest run record
        latest = (
            db.query(JobRun)
            .filter(JobRun.job_id == job.id)
            .order_by(JobRun.started_at.desc())
            .first()
        )

        result.append({
            "id": job.id,
            "name": meta.get("name", job.id),
            "description": meta.get("description", ""),
            "trigger": trigger_str,
            "next_run_time": next_run,
            "latest_run": {
                "started_at": str(latest.started_at) if latest else None,
                "finished_at": str(latest.finished_at) if latest else None,
                "status": latest.status if latest else None,
                "summary": latest.summary if latest else None,
            } if latest else None,
        })

    return ok(result)


@router.get("/jobs/{job_id}/history")
def job_history(
    job_id: str,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """Get run history for a specific job."""
    runs = (
        db.query(JobRun)
        .filter(JobRun.job_id == job_id)
        .order_by(JobRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return ok([
        {
            "id": r.id,
            "started_at": str(r.started_at),
            "finished_at": str(r.finished_at) if r.finished_at else None,
            "status": r.status,
            "summary": r.summary,
        }
        for r in runs
    ])


@router.post("/jobs/{job_id}/run")
def trigger_job(job_id: str):
    """Manually trigger a job."""
    job = scheduler.get_job(job_id)
    if not job:
        return ok(None, meta={"error": f"Job {job_id} not found"})
    job.modify(next_run_time=None)  # Reset to run immediately
    scheduler.modify_job(job_id, next_run_time=None)
    # Actually run it directly in a thread-safe way
    try:
        job.func()
        return ok({"triggered": True, "job_id": job_id})
    except Exception as e:
        return ok({"triggered": True, "job_id": job_id, "error": str(e)})
