import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.response import ok
from app.services.rebalance_service import get_rebalance_analysis, get_targets, set_targets

logger = logging.getLogger(__name__)

router = APIRouter()


class TargetItem(BaseModel):
    category_id: int
    target_pct: float


class SetTargetsRequest(BaseModel):
    targets: list[TargetItem]


@router.get("/targets")
def api_get_targets(db: Session = Depends(get_db)):
    """获取当前目标配置。"""
    return ok(get_targets(db))


@router.post("/targets")
def api_set_targets(body: SetTargetsRequest, db: Session = Depends(get_db)):
    """设置目标配置。"""
    count = set_targets(db, [t.model_dump() for t in body.targets])
    return ok({"updated": count})


@router.get("/analysis")
def api_rebalance_analysis(db: Session = Depends(get_db)):
    """偏离分析 + 再平衡建议。"""
    return ok(get_rebalance_analysis(db))
