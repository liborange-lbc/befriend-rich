import json
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_openid_optional
from app.database import get_db
from app.models.portfolio import PortfolioSnapshot
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


@router.get("/asset-history")
def api_asset_history(
    model: str = Query(default="良田模型"),
    weeks: int = Query(default=12, ge=1, le=52),
    openid: str | None = Depends(get_openid_optional),
    db: Session = Depends(get_db),
):
    """按周返回某个模型分类的资产金额历史，用于资产变化图。"""
    if openid is None:
        openid_filter = True
    else:
        openid_filter = or_(PortfolioSnapshot.openid == openid, PortfolioSnapshot.openid.is_(None))

    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(openid_filter)
        .order_by(PortfolioSnapshot.snapshot_date.desc())
        .limit(weeks)
        .all()
    )
    snapshots = list(reversed(snapshots))

    result = []
    for s in snapshots:
        try:
            breakdown = json.loads(s.model_breakdown) if isinstance(s.model_breakdown, str) else s.model_breakdown
        except Exception:
            breakdown = {}
        categories = breakdown.get(model, {})
        result.append({
            "date": s.snapshot_date.isoformat(),
            "total": round(s.total_amount_cny, 2),
            "categories": {k: round(v, 2) for k, v in categories.items()},
        })

    # 收集所有出现的分类名
    all_keys: list[str] = []
    seen: set[str] = set()
    for r in result:
        for k in r["categories"]:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)

    return ok({"series": result, "category_keys": all_keys})
