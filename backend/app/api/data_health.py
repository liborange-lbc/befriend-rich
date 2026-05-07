import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.ai_repair_service import ai_diagnose_and_repair
from app.services.data_health_service import (
    get_data_source_overview,
    get_fund_coverage,
    get_job_history,
    repair_fund_coverage,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview")
def api_data_health_overview(db: Session = Depends(get_db)):
    """所有数据源的健康状态概览。"""
    return ok(get_data_source_overview(db))


@router.get("/fund-coverage")
def api_fund_coverage(db: Session = Depends(get_db)):
    """每个活跃基金的数据覆盖情况。"""
    return ok(get_fund_coverage(db))


@router.post("/repair")
def api_repair_fund_coverage(db: Session = Depends(get_db)):
    """修复异常基金数据：回填 gap_days > 3 的基金。"""
    results = repair_fund_coverage(db)
    repaired = sum(1 for r in results if r["status"] == "repaired")
    return ok({
        "total": len(results),
        "repaired": repaired,
        "details": results,
    })


@router.post("/ai-diagnose")
def api_ai_diagnose(db: Session = Depends(get_db)):
    """AI 自动诊断并修复系统异常。"""
    result = ai_diagnose_and_repair(db)
    return ok(result)


@router.get("/job-history")
def api_job_history(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    """最近任务执行历史。"""
    return ok(get_job_history(db, limit))
