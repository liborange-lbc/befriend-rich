import json
import logging
import os
from datetime import datetime, timedelta

from garminconnect import Garmin

from app.database import SessionLocal
from app.models.watch import WatchActivity, WatchConnection

logger = logging.getLogger(__name__)

TOKENSTORE_DIR = os.path.join("data", "garmin_tokens")

# Garmin activityType.typeKey → normalized sport_type
_SPORT_MAP = {
    "running": "run",
    "trail_running": "run",
    "treadmill_running": "run",
    "cycling": "ride",
    "mountain_biking": "ride",
    "indoor_cycling": "ride",
    "virtual_ride": "ride",
    "swimming": "swim",
    "lap_swimming": "swim",
    "open_water_swimming": "swim",
    "hiking": "hike",
    "walking": "walk",
    "strength_training": "strength",
    "yoga": "yoga",
    "elliptical": "elliptical",
    "stair_climbing": "stair",
    "rowing": "rowing",
    "skiing": "ski",
    "snowboarding": "snowboard",
    "other": "other",
}


def _normalize_sport(type_key: str) -> str:
    return _SPORT_MAP.get(type_key, type_key or "other")


def _parse_garmin_time(time_str: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return datetime.now()


def test_garmin_login(email: str, password: str) -> dict:
    os.makedirs(TOKENSTORE_DIR, exist_ok=True)
    tokenstore_path = os.path.join(TOKENSTORE_DIR, "tokens")
    client = Garmin(email, password)
    client.login(tokenstore_path)
    display_name = client.get_full_name() or email
    return {"display_name": display_name}


def sync_garmin_activities(connection: WatchConnection, days: int = 2) -> dict:
    creds = json.loads(connection.credentials)
    email = creds.get("email", "")
    password = creds.get("password", "")
    openid = connection.openid

    os.makedirs(TOKENSTORE_DIR, exist_ok=True)
    tokenstore_path = os.path.join(TOKENSTORE_DIR, "tokens")

    client = Garmin(email, password)
    client.login(tokenstore_path)

    # Fetch enough activities to cover the requested period
    fetch_limit = 100 if days <= 30 else 500
    activities = client.get_activities(start=0, limit=fetch_limit)

    cutoff = datetime.now() - timedelta(days=days)
    synced = 0
    errors = []

    db = SessionLocal()
    try:
        for act in activities:
            try:
                start_time_str = act.get("startTimeLocal", "")
                if not start_time_str:
                    continue
                start_time = _parse_garmin_time(start_time_str)
                if start_time < cutoff:
                    continue

                source_id = str(act.get("activityId", ""))
                existing = db.query(WatchActivity).filter(
                    WatchActivity.source == "garmin",
                    WatchActivity.source_id == source_id,
                ).first()
                if existing:
                    continue

                type_key = ""
                activity_type = act.get("activityType")
                if isinstance(activity_type, dict):
                    type_key = activity_type.get("typeKey", "")

                duration = act.get("duration", 0) or 0
                distance = act.get("distance", None)
                avg_speed_mps = act.get("averageSpeed", None)

                avg_pace = None
                avg_speed_kph = None
                if avg_speed_mps and avg_speed_mps > 0:
                    avg_speed_kph = round(avg_speed_mps * 3.6, 2)
                    avg_pace = round(1000.0 / avg_speed_mps, 1)

                record = WatchActivity(
                    openid=openid,
                    source="garmin",
                    source_id=source_id,
                    sport_type=_normalize_sport(type_key),
                    name=act.get("activityName", "") or "",
                    start_time=start_time,
                    duration_seconds=int(duration),
                    distance_meters=round(distance, 1) if distance else None,
                    calories=act.get("calories", None),
                    avg_heart_rate=act.get("averageHR", None),
                    max_heart_rate=act.get("maxHR", None),
                    avg_pace=avg_pace,
                    avg_speed=avg_speed_kph,
                    elevation_gain=act.get("elevationGain", None),
                )
                db.add(record)
                synced += 1
            except Exception as e:
                errors.append(f"Activity {act.get('activityId', '?')}: {e}")
                logger.warning("Failed to process garmin activity: %s", e)

        if synced > 0:
            db.commit()

        connection.last_sync_at = datetime.now()
        connection.status = "active"
        connection.error_message = None
        db_main = SessionLocal()
        try:
            conn = db_main.query(WatchConnection).get(connection.id)
            if conn:
                conn.last_sync_at = connection.last_sync_at
                conn.status = "active"
                conn.error_message = None
                db_main.commit()
        finally:
            db_main.close()

    except Exception as e:
        logger.error("Garmin sync failed: %s", e)
        db_main = SessionLocal()
        try:
            conn = db_main.query(WatchConnection).get(connection.id)
            if conn:
                conn.status = "error"
                conn.error_message = str(e)[:500]
                db_main.commit()
        finally:
            db_main.close()
        raise
    finally:
        db.close()

    return {"source": "garmin", "synced": synced, "errors": errors}
