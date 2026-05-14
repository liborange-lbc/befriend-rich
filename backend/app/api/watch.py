import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_openid
from app.database import get_db
from app.models.watch import GarminDailySummary, WatchActivity, WatchConnection
from app.response import fail, ok
from app.schemas.watch import GarminConnectRequest, StravaCallbackRequest
from app.services.watch.garmin_service import sync_garmin_activities, test_garmin_login
from app.services.watch.strava_service import (
    exchange_strava_code,
    get_strava_auth_url,
    handle_strava_webhook,
    sync_strava_activities,
)
from app.services.watch.sync_service import sync_all_connections

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Connection management ──


@router.get("/connections")
def list_connections(openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    rows = db.query(WatchConnection).filter(WatchConnection.openid == openid).order_by(WatchConnection.created_at).all()
    result = []
    for r in rows:
        result.append({
            "id": r.id,
            "source": r.source,
            "status": r.status,
            "last_sync_at": str(r.last_sync_at) if r.last_sync_at else None,
            "error_message": r.error_message,
            "created_at": str(r.created_at) if r.created_at else None,
        })
    return ok(result)


@router.post("/connections/garmin")
def connect_garmin(body: GarminConnectRequest, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    try:
        info = test_garmin_login(body.email, body.password)
    except Exception as e:
        return fail(f"佳明登录失败: {e}")

    existing = db.query(WatchConnection).filter(WatchConnection.source == "garmin", WatchConnection.openid == openid).first()
    creds = json.dumps({"email": body.email, "password": body.password})

    if existing:
        existing.credentials = creds
        existing.status = "active"
        existing.error_message = None
    else:
        existing = WatchConnection(source="garmin", status="active", credentials=creds, openid=openid)
        db.add(existing)

    db.commit()
    db.refresh(existing)

    return ok({
        "id": existing.id,
        "source": "garmin",
        "status": "active",
        "display_name": info.get("display_name", ""),
    })


@router.get("/connections/strava/auth-url")
def strava_auth_url():
    url = get_strava_auth_url()
    return ok({"url": url})


@router.get("/strava/callback")
def strava_callback(code: str = Query(...), openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    try:
        token_data = exchange_strava_code(code)
    except Exception as e:
        return fail(f"Strava 授权失败: {e}")

    existing = db.query(WatchConnection).filter(WatchConnection.source == "strava", WatchConnection.openid == openid).first()
    creds = json.dumps({
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": token_data["expires_at"],
        "athlete_id": token_data["athlete_id"],
    })

    if existing:
        existing.credentials = creds
        existing.status = "active"
        existing.error_message = None
    else:
        existing = WatchConnection(source="strava", status="active", credentials=creds, openid=openid)
        db.add(existing)

    db.commit()
    db.refresh(existing)

    return ok({
        "id": existing.id,
        "source": "strava",
        "status": "active",
        "athlete_name": token_data.get("athlete_name", ""),
    })


@router.delete("/connections/{connection_id}")
def delete_connection(connection_id: int, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    conn = db.query(WatchConnection).filter(WatchConnection.id == connection_id, WatchConnection.openid == openid).first()
    if not conn:
        return fail("连接不存在", 404)
    db.delete(conn)
    db.commit()
    return ok({"deleted": connection_id})


# ── Strava webhook ──


@router.get("/strava/webhook")
def strava_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Strava webhook subscription verification (GET)."""
    return {"hub.challenge": hub_challenge}


@router.post("/strava/webhook")
def strava_webhook_receive(event: dict):
    """Strava webhook event receiver (POST)."""
    try:
        handle_strava_webhook(event)
    except Exception as e:
        logger.error("Strava webhook handling failed: %s", e)
    return ok()


# ── Sync ──


@router.post("/sync")
def manual_sync(days: int = Query(7, ge=1, le=3650), openid: str = Depends(get_openid)):
    results = sync_all_connections(days=days, openid=openid)
    return ok(results)


@router.post("/sync/{connection_id}")
def sync_single(connection_id: int, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    conn = db.query(WatchConnection).filter(WatchConnection.id == connection_id, WatchConnection.openid == openid).first()
    if not conn:
        return fail("连接不存在", 404)

    try:
        if conn.source == "garmin":
            result = sync_garmin_activities(conn, days=7)
        elif conn.source == "strava":
            result = sync_strava_activities(conn, days=7)
        else:
            return fail(f"未知来源: {conn.source}")
    except Exception as e:
        return fail(f"同步失败: {e}")

    return ok(result)


# ── Activities ──


@router.get("/activities")
def list_activities(
    sport_type: str | None = Query(None),
    source: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    query = db.query(WatchActivity).filter(WatchActivity.openid == openid)

    if sport_type:
        query = query.filter(WatchActivity.sport_type == sport_type)
    if source:
        query = query.filter(WatchActivity.source == source)
    if start_date:
        query = query.filter(WatchActivity.start_time >= str(start_date))
    if end_date:
        next_day = end_date + timedelta(days=1)
        query = query.filter(WatchActivity.start_time < str(next_day))

    total = query.count()
    rows = query.order_by(desc(WatchActivity.start_time)).offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for r in rows:
        items.append({
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
        })

    return ok(items, meta={"total": total, "page": page, "per_page": per_page})


@router.get("/activities/{activity_id}")
def get_activity(activity_id: int, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    row = db.query(WatchActivity).filter(WatchActivity.id == activity_id, WatchActivity.openid == openid).first()
    if not row:
        return fail("活动不存在", 404)
    result = {
        "id": row.id,
        "source": row.source,
        "source_id": row.source_id,
        "sport_type": row.sport_type,
        "name": row.name,
        "start_time": str(row.start_time) if row.start_time else None,
        "duration_seconds": row.duration_seconds,
        "distance_meters": row.distance_meters,
        "calories": row.calories,
        "avg_heart_rate": row.avg_heart_rate,
        "max_heart_rate": row.max_heart_rate,
        "avg_pace": row.avg_pace,
        "avg_speed": row.avg_speed,
        "elevation_gain": row.elevation_gain,
    }
    if row.detail_json:
        try:
            result["detail"] = json.loads(row.detail_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return ok(result)


@router.get("/summary")
def get_summary(
    days: int = Query(30, ge=1, le=365),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    rows = db.query(WatchActivity).filter(WatchActivity.openid == openid, WatchActivity.start_time >= str(since)).all()

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


# ── Daily Health ──


@router.get("/daily-health")
def get_daily_health(
    target_date: date | None = Query(None, description="日期，默认今天"),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    if not target_date:
        target_date = date.today()
    row = db.query(GarminDailySummary).filter(
        GarminDailySummary.date == target_date,
        GarminDailySummary.openid == openid,
    ).first()
    if not row:
        return ok(None)
    return ok({
        "date": row.date.isoformat(),
        "steps": row.steps,
        "floors_climbed": row.floors_climbed,
        "active_minutes": row.active_minutes,
        "intensity_minutes": row.intensity_minutes,
        "calories_total": row.calories_total,
        "distance_meters": row.distance_meters,
        "resting_hr": row.resting_hr,
        "min_hr": row.min_hr,
        "max_hr": row.max_hr,
        "body_battery_high": row.body_battery_high,
        "body_battery_low": row.body_battery_low,
        "avg_stress": row.avg_stress,
        "max_stress": row.max_stress,
        "sleep_score": row.sleep_score,
        "sleep_start": row.sleep_start,
        "sleep_end": row.sleep_end,
        "sleep_duration_seconds": row.sleep_duration_seconds,
        "deep_sleep_seconds": row.deep_sleep_seconds,
        "light_sleep_seconds": row.light_sleep_seconds,
        "rem_sleep_seconds": row.rem_sleep_seconds,
        "awake_seconds": row.awake_seconds,
        "avg_spo2": row.avg_spo2,
        "avg_respiration": row.avg_respiration,
    })


@router.get("/daily-health/range")
def get_daily_health_range(
    start_date: date = Query(...),
    end_date: date | None = Query(None),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    if not end_date:
        end_date = date.today()
    rows = (
        db.query(GarminDailySummary)
        .filter(
            GarminDailySummary.openid == openid,
            GarminDailySummary.date >= start_date,
            GarminDailySummary.date <= end_date,
        )
        .order_by(GarminDailySummary.date)
        .all()
    )
    return ok([{
        "date": r.date.isoformat(),
        "steps": r.steps,
        "resting_hr": r.resting_hr,
        "body_battery_high": r.body_battery_high,
        "body_battery_low": r.body_battery_low,
        "avg_stress": r.avg_stress,
        "sleep_score": r.sleep_score,
        "sleep_duration_seconds": r.sleep_duration_seconds,
        "deep_sleep_seconds": r.deep_sleep_seconds,
        "light_sleep_seconds": r.light_sleep_seconds,
        "rem_sleep_seconds": r.rem_sleep_seconds,
        "avg_spo2": r.avg_spo2,
        "calories_total": r.calories_total,
    } for r in rows])
