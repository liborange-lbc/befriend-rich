from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.deps import get_openid
from app.database import get_db
from app.models.baduanjin import BaduanjinRecord
from app.response import ok

TYPE_NAMES = {
    "baduanjin": "八段锦",
    "jingang": "金刚功",
    "taichi": "太极",
}

router = APIRouter()


@router.post("/checkin")
def checkin(
    duration_seconds: int = Query(..., ge=1),
    exercise_type: str = Query("baduanjin"),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    today = date.today()
    record = BaduanjinRecord(
        openid=openid,
        date=today,
        exercise_type=exercise_type,
        duration_seconds=duration_seconds,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ok({
        "id": record.id,
        "date": str(record.date),
        "exercise_type": record.exercise_type,
        "duration_seconds": record.duration_seconds,
    })


@router.get("/records")
def list_records(
    days: int = Query(30, ge=1, le=365),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(BaduanjinRecord)
        .filter(BaduanjinRecord.openid == openid, BaduanjinRecord.date >= since)
        .order_by(desc(BaduanjinRecord.date))
        .all()
    )
    items = [
        {
            "id": r.id,
            "date": str(r.date),
            "exercise_type": r.exercise_type,
            "type_name": TYPE_NAMES.get(r.exercise_type, r.exercise_type),
            "duration_seconds": r.duration_seconds,
        }
        for r in rows
    ]
    return ok(items)


@router.get("/stats")
def stats(
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    today = date.today()
    total = db.query(func.count(BaduanjinRecord.id)).filter(
        BaduanjinRecord.openid == openid
    ).scalar() or 0

    month_start = today.replace(day=1)
    month_count = db.query(func.count(BaduanjinRecord.id)).filter(
        BaduanjinRecord.openid == openid,
        BaduanjinRecord.date >= month_start,
    ).scalar() or 0

    # Calculate streak (consecutive days)
    dates = (
        db.query(BaduanjinRecord.date)
        .filter(BaduanjinRecord.openid == openid)
        .distinct()
        .order_by(desc(BaduanjinRecord.date))
        .all()
    )
    streak = 0
    check = today
    for (d,) in dates:
        if d == check:
            streak += 1
            check -= timedelta(days=1)
        elif d < check:
            break

    today_done = any(d == today for (d,) in dates)

    return ok({
        "total": total,
        "month_count": month_count,
        "streak": streak,
        "today_done": today_done,
    })
