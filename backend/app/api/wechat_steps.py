from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.wechat_steps import WechatStep
from app.response import ok

router = APIRouter()

STEP_GOAL = 10000


class StepItem(BaseModel):
    date: date
    steps: int


class SyncRequest(BaseModel):
    steps: list[StepItem]


@router.post("/sync")
def sync_steps(body: SyncRequest, db: Session = Depends(get_db)):
    count = 0
    for item in body.steps:
        existing = db.query(WechatStep).filter(WechatStep.date == item.date).first()
        if existing:
            existing.steps = item.steps
        else:
            db.add(WechatStep(date=item.date, steps=item.steps))
        count += 1
    db.commit()
    return ok({"synced": count})


@router.get("/history")
def get_history(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    rows = (
        db.query(WechatStep)
        .filter(WechatStep.date >= start_date, WechatStep.date <= end_date)
        .order_by(WechatStep.date)
        .all()
    )
    return ok([{"date": str(r.date), "steps": r.steps} for r in rows])


@router.get("/stats")
def get_stats(days: int = Query(30), db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    rows = db.query(WechatStep).filter(WechatStep.date >= since).all()

    if not rows:
        return ok({
            "avg_daily": 0,
            "max_steps": 0,
            "max_date": None,
            "total": 0,
            "achievement_days": 0,
            "goal": STEP_GOAL,
        })

    total = sum(r.steps for r in rows)
    max_row = max(rows, key=lambda r: r.steps)
    achievement_days = sum(1 for r in rows if r.steps >= STEP_GOAL)

    return ok({
        "avg_daily": total // len(rows),
        "max_steps": max_row.steps,
        "max_date": str(max_row.date),
        "total": total,
        "achievement_days": achievement_days,
        "goal": STEP_GOAL,
    })
