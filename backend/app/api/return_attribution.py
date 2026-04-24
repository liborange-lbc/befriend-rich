import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.return_attribution_service import (
    get_attribution_by_category,
    get_attribution_by_fund,
    get_attribution_summary,
    get_twr_curve,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary")
def api_attribution_summary(db: Session = Depends(get_db)):
    """总体收益归因概览。"""
    return ok(get_attribution_summary(db))


@router.get("/by-fund")
def api_attribution_by_fund(db: Session = Depends(get_db)):
    """按基金的收益贡献。"""
    return ok(get_attribution_by_fund(db))


@router.get("/by-category")
def api_attribution_by_category(db: Session = Depends(get_db)):
    """按分类的收益贡献。"""
    return ok(get_attribution_by_category(db))


@router.get("/twr")
def api_twr_curve(db: Session = Depends(get_db)):
    """时间加权收益率曲线。"""
    return ok(get_twr_curve(db))
