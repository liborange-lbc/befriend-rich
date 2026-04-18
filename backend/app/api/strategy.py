from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.strategy import AlertLog, Strategy
from app.response import ok
from app.schemas.strategy import (
    AlertLogResponse,
    StrategyCreate,
    StrategyResponse,
    StrategyUpdate,
)

router = APIRouter()


@router.post("")
def create_strategy(body: StrategyCreate, db: Session = Depends(get_db)):
    strategy = Strategy(**body.model_dump())
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return ok(StrategyResponse.model_validate(strategy).model_dump())


@router.get("")
def list_strategies(
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Strategy)
    if is_active is not None:
        query = query.filter(Strategy.is_active == is_active)
    strategies = query.all()
    return ok([StrategyResponse.model_validate(s).model_dump() for s in strategies])


@router.get("/{strategy_id}")
def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return ok(StrategyResponse.model_validate(strategy).model_dump())


@router.put("/{strategy_id}")
def update_strategy(strategy_id: int, body: StrategyUpdate, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(strategy, key, value)
    db.commit()
    db.refresh(strategy)
    return ok(StrategyResponse.model_validate(strategy).model_dump())


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")
    db.delete(strategy)
    db.commit()
    return ok({"deleted": True})


@router.get("/alerts/recent")
def get_recent_alerts(limit: int = Query(default=20), db: Session = Depends(get_db)):
    alerts = (
        db.query(AlertLog)
        .order_by(AlertLog.id.desc())
        .limit(limit)
        .all()
    )
    return ok([AlertLogResponse.model_validate(a).model_dump() for a in alerts])
