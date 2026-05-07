import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import fail, ok
from app.services.allocation_engine import (
    calculate_optimal_allocation,
    get_allocation_history,
    get_current_allocation,
    get_deviation_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class CalculateRequest(BaseModel):
    trigger: str = "manual"


@router.get("/current")
def current_allocation(
    model_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """当前配置目标权重列表。"""
    targets = get_current_allocation(db, model_id)
    return ok(targets)


@router.post("/calculate")
def trigger_calculation(
    body: CalculateRequest,
    model_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """触发重新计算最优配置。"""
    try:
        result = calculate_optimal_allocation(db, model_id, trigger=body.trigger)
    except Exception as e:
        logger.error("Allocation calculation failed: %s", e, exc_info=True)
        return fail(f"配置计算失败: {e}", status_code=500)

    if "error" in result:
        return fail(result["error"])
    return ok(result)


@router.get("/history")
def allocation_history(
    model_id: int = Query(default=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """历史配置快照（分页）。"""
    offset = (page - 1) * page_size
    data, total = get_allocation_history(db, model_id, limit=page_size, offset=offset)
    return ok(data, meta={"total": total, "page": page, "page_size": page_size})


@router.get("/deviation")
def deviation_summary(
    model_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """当前偏离度摘要及再平衡建议。"""
    summary = get_deviation_summary(db, model_id)
    return ok(summary)


@router.get("/metrics")
def category_metrics(
    model_id: int = Query(default=1),
    db: Session = Depends(get_db),
):
    """各类别风险收益指标（收益率/波动率/夏普/最大回撤）。"""
    targets = get_current_allocation(db, model_id)
    metrics = [
        {
            "category_id": t["category_id"],
            "category_name": t["category_name"],
            "parent_name": t["parent_name"],
            "annual_return": t["annual_return"],
            "volatility": t["volatility"],
            "max_drawdown": t["max_drawdown"],
            "sharpe_ratio": t["sharpe_ratio"],
        }
        for t in targets
    ]
    return ok(metrics)
