import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.fund_stats_service import (
    get_all_fund_stats,
    get_normalized_prices,
    get_ranking_by_classification,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats")
def api_fund_stats(db: Session = Depends(get_db)):
    """所有活跃基金的风险收益指标。"""
    return ok(get_all_fund_stats(db))


@router.get("/prices")
def api_normalized_prices(
    fund_ids: str = Query(..., description="逗号分隔的基金ID"),
    start_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """多基金归一化价格序列（叠加对比用）。"""
    ids = [int(x.strip()) for x in fund_ids.split(",") if x.strip()]
    return ok(get_normalized_prices(db, ids, start_date))


@router.get("/ranking")
def api_fund_ranking(db: Session = Depends(get_db)):
    """按良田模型分类的同类排名。"""
    return ok(get_ranking_by_classification(db))
