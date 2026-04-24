import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.correlation_service import (
    get_correlation_matrix,
    get_diversification_score,
    get_holding_overlap,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/matrix")
def api_correlation_matrix(
    lookback_days: int = Query(default=365, ge=30, le=3650),
    db: Session = Depends(get_db),
):
    """基金收益率相关性矩阵。"""
    return ok(get_correlation_matrix(db, lookback_days))


@router.get("/overlap")
def api_holding_overlap(db: Session = Depends(get_db)):
    """持仓重叠矩阵（Jaccard 相似度）。"""
    return ok(get_holding_overlap(db))


@router.get("/diversification-score")
def api_diversification_score(
    lookback_days: int = Query(default=365, ge=30, le=3650),
    db: Session = Depends(get_db),
):
    """组合分散度评分。"""
    return ok(get_diversification_score(db, lookback_days))
