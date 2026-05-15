import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.deps import get_openid
from app.database import get_db
from app.models.exercise import ExerciseRecord
from app.response import fail, ok

logger = logging.getLogger(__name__)

SPORT_LABELS = {
    "baduanjin": "八段锦",
    "jingang": "金刚功",
    "taichi": "太极",
    "run": "跑步",
    "ride": "骑行",
    "swim": "游泳",
    "hike": "徒步",
    "walk": "步行",
    "strength": "力量训练",
    "yoga": "瑜伽",
    "elliptical": "椭圆机",
    "rowing": "划船",
    "ski": "滑雪",
    "snowboard": "单板滑雪",
}

router = APIRouter()


def _serialize(r: ExerciseRecord) -> dict:
    return {
        "id": r.id,
        "source": r.source,
        "source_id": r.source_id,
        "sport_type": r.sport_type,
        "name": r.name,
        "start_time": str(r.start_time) if r.start_time else None,
        "duration_seconds": r.duration_seconds,
        "distance_meters": r.distance_meters,
        "calories": r.calories,
        "avg_heart_rate": r.avg_heart_rate,
        "max_heart_rate": r.max_heart_rate,
        "avg_pace": r.avg_pace,
        "avg_speed": r.avg_speed,
        "elevation_gain": r.elevation_gain,
    }


# ── List / Query ──


@router.get("/activities")
def list_activities(
    sport_type: str | None = Query(None),
    source: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=500),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    query = db.query(ExerciseRecord).filter(ExerciseRecord.openid == openid)

    if sport_type:
        query = query.filter(ExerciseRecord.sport_type == sport_type)
    if source:
        query = query.filter(ExerciseRecord.source == source)
    if start_date:
        query = query.filter(ExerciseRecord.start_time >= str(start_date))
    if end_date:
        next_day = end_date + timedelta(days=1)
        query = query.filter(ExerciseRecord.start_time < str(next_day))

    total = query.count()
    rows = (
        query.order_by(desc(ExerciseRecord.start_time))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return ok([_serialize(r) for r in rows], meta={"total": total, "page": page, "per_page": per_page})


@router.get("/activities/{activity_id}")
def get_activity(
    activity_id: int,
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    row = db.query(ExerciseRecord).filter(
        ExerciseRecord.id == activity_id,
        ExerciseRecord.openid == openid,
    ).first()
    if not row:
        return fail("记录不存在", 404)
    result = _serialize(row)
    if row.detail_json:
        import json
        try:
            result["detail"] = json.loads(row.detail_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return ok(result)


# ── Summary ──


@router.get("/summary")
def get_summary(
    days: int = Query(30, ge=1, le=365),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    rows = db.query(ExerciseRecord).filter(
        ExerciseRecord.openid == openid,
        ExerciseRecord.start_time >= str(since),
    ).all()

    if not rows:
        return ok({
            "total_activities": 0,
            "total_duration_seconds": 0,
            "total_distance_meters": 0,
            "total_calories": 0,
            "by_sport": {},
        })

    total_duration = sum(r.duration_seconds for r in rows)
    total_distance = sum(r.distance_meters or 0 for r in rows)
    total_calories = sum(r.calories or 0 for r in rows)

    by_sport = {}
    for r in rows:
        sport = r.sport_type
        if sport not in by_sport:
            by_sport[sport] = {"count": 0, "duration_seconds": 0, "distance_meters": 0}
        by_sport[sport]["count"] += 1
        by_sport[sport]["duration_seconds"] += r.duration_seconds
        by_sport[sport]["distance_meters"] += r.distance_meters or 0

    return ok({
        "total_activities": len(rows),
        "total_duration_seconds": total_duration,
        "total_distance_meters": round(total_distance, 1),
        "total_calories": total_calories,
        "by_sport": by_sport,
    })


# ── Checkin (replaces baduanjin checkin) ──


@router.post("/checkin")
def checkin(
    duration_seconds: int = Query(..., ge=1),
    exercise_type: str = Query("baduanjin"),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    record = ExerciseRecord(
        openid=openid,
        source="checkin",
        source_id=None,
        sport_type=exercise_type,
        name=SPORT_LABELS.get(exercise_type, exercise_type),
        start_time=now,
        duration_seconds=duration_seconds,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ok({
        "id": record.id,
        "date": now.strftime("%Y-%m-%d"),
        "exercise_type": record.sport_type,
        "duration_seconds": record.duration_seconds,
    })


# ── Checkin stats (replaces baduanjin stats) ──


@router.get("/checkin/stats")
def checkin_stats(
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    today = date.today()
    today_str = today.isoformat()
    tomorrow_str = (today + timedelta(days=1)).isoformat()

    total = db.query(func.count(ExerciseRecord.id)).filter(
        ExerciseRecord.openid == openid,
        ExerciseRecord.source == "checkin",
    ).scalar() or 0

    month_start = today.replace(day=1).isoformat()
    month_count = db.query(func.count(ExerciseRecord.id)).filter(
        ExerciseRecord.openid == openid,
        ExerciseRecord.source == "checkin",
        ExerciseRecord.start_time >= month_start,
    ).scalar() or 0

    # Streak: consecutive days with checkin
    dates = (
        db.query(func.date(ExerciseRecord.start_time))
        .filter(
            ExerciseRecord.openid == openid,
            ExerciseRecord.source == "checkin",
        )
        .distinct()
        .order_by(desc(func.date(ExerciseRecord.start_time)))
        .all()
    )
    streak = 0
    check = today
    for (d,) in dates:
        d_date = d if isinstance(d, date) else date.fromisoformat(str(d))
        if d_date == check:
            streak += 1
            check -= timedelta(days=1)
        elif d_date < check:
            break

    today_done = db.query(func.count(ExerciseRecord.id)).filter(
        ExerciseRecord.openid == openid,
        ExerciseRecord.source == "checkin",
        ExerciseRecord.start_time >= today_str,
        ExerciseRecord.start_time < tomorrow_str,
    ).scalar() > 0

    return ok({
        "total": total,
        "month_count": month_count,
        "streak": streak,
        "today_done": today_done,
    })


# ── Checkin records ──


@router.get("/checkin/records")
def checkin_records(
    days: int = Query(30, ge=1, le=365),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = (
        db.query(ExerciseRecord)
        .filter(
            ExerciseRecord.openid == openid,
            ExerciseRecord.source == "checkin",
            ExerciseRecord.start_time >= since,
        )
        .order_by(desc(ExerciseRecord.start_time))
        .all()
    )
    return ok([
        {
            "id": r.id,
            "date": str(r.start_time)[:10] if r.start_time else None,
            "exercise_type": r.sport_type,
            "type_name": SPORT_LABELS.get(r.sport_type, r.sport_type),
            "duration_seconds": r.duration_seconds,
        }
        for r in rows
    ])
