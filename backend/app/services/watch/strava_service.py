import json
import logging
import time
from datetime import datetime, timedelta

import httpx

from app.database import SessionLocal
from app.models.watch import WatchActivity, WatchConnection
from app.services.config_service import get_config

logger = logging.getLogger(__name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

# Strava sport_type → normalized sport_type
_SPORT_MAP = {
    "Run": "run",
    "TrailRun": "run",
    "VirtualRun": "run",
    "Ride": "ride",
    "MountainBikeRide": "ride",
    "GravelRide": "ride",
    "EBikeRide": "ride",
    "VirtualRide": "ride",
    "Swim": "swim",
    "Hike": "hike",
    "Walk": "walk",
    "WeightTraining": "strength",
    "Yoga": "yoga",
    "Rowing": "rowing",
    "Elliptical": "elliptical",
    "StairStepper": "stair",
    "AlpineSki": "ski",
    "Snowboard": "snowboard",
}


def _normalize_sport(sport_type: str) -> str:
    return _SPORT_MAP.get(sport_type, sport_type.lower() if sport_type else "other")


def get_strava_auth_url() -> str:
    client_id = get_config("strava_client_id", "")
    redirect_uri = get_config("strava_redirect_uri", "https://liborange.asia/api/v1/watch/strava/callback")
    return (
        f"{STRAVA_AUTH_URL}?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code&approval_prompt=auto"
        f"&scope=activity:read_all"
    )


def exchange_strava_code(code: str) -> dict:
    client_id = get_config("strava_client_id", "")
    client_secret = get_config("strava_client_secret", "")

    resp = httpx.post(STRAVA_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    data = resp.json()

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": data["expires_at"],
        "athlete_id": data["athlete"]["id"],
        "athlete_name": f"{data['athlete'].get('firstname', '')} {data['athlete'].get('lastname', '')}".strip(),
    }


def _refresh_token_if_needed(creds: dict) -> dict:
    expires_at = creds.get("expires_at", 0)
    if time.time() < expires_at - 300:
        return creds

    client_id = get_config("strava_client_id", "")
    client_secret = get_config("strava_client_secret", "")

    resp = httpx.post(STRAVA_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
    })
    resp.raise_for_status()
    data = resp.json()

    creds["access_token"] = data["access_token"]
    creds["refresh_token"] = data["refresh_token"]
    creds["expires_at"] = data["expires_at"]
    return creds


def _detect_device_source(activity: dict) -> str:
    device_name = (activity.get("device_name") or "").lower()
    gear_id = (activity.get("gear_id") or "").lower()
    external_id = (activity.get("external_id") or "").lower()

    if "coros" in device_name or "coros" in external_id:
        return "coros"
    if "huawei" in device_name or "honor" in device_name:
        return "huawei"
    if "garmin" in device_name:
        return "garmin"
    return "strava"


def sync_strava_activities(connection: WatchConnection, days: int = 2) -> dict:
    creds = json.loads(connection.credentials)
    creds = _refresh_token_if_needed(creds)

    # Persist refreshed tokens
    db_update = SessionLocal()
    try:
        conn = db_update.query(WatchConnection).get(connection.id)
        if conn:
            conn.credentials = json.dumps(creds)
            db_update.commit()
    finally:
        db_update.close()

    access_token = creds["access_token"]
    after_ts = int((datetime.now() - timedelta(days=days)).timestamp())

    headers = {"Authorization": f"Bearer {access_token}"}
    resp = httpx.get(
        f"{STRAVA_API_BASE}/athlete/activities",
        headers=headers,
        params={"after": after_ts, "per_page": 100},
    )
    resp.raise_for_status()
    activities = resp.json()

    synced = 0
    errors = []

    db = SessionLocal()
    try:
        for act in activities:
            try:
                source_id = str(act["id"])
                existing = db.query(WatchActivity).filter(
                    WatchActivity.source_id == source_id,
                ).first()
                if existing:
                    continue

                start_time = datetime.fromisoformat(act["start_date_local"].replace("Z", "+00:00")).replace(tzinfo=None)
                sport_type = act.get("sport_type") or act.get("type") or "Other"
                distance = act.get("distance")
                moving_time = act.get("moving_time", 0)

                avg_speed_mps = act.get("average_speed")
                avg_pace = None
                avg_speed_kph = None
                if avg_speed_mps and avg_speed_mps > 0:
                    avg_speed_kph = round(avg_speed_mps * 3.6, 2)
                    avg_pace = round(1000.0 / avg_speed_mps, 1)

                source = _detect_device_source(act)

                record = WatchActivity(
                    source=source,
                    source_id=source_id,
                    sport_type=_normalize_sport(sport_type),
                    name=act.get("name", ""),
                    start_time=start_time,
                    duration_seconds=moving_time,
                    distance_meters=round(distance, 1) if distance else None,
                    calories=int(act["calories"]) if act.get("calories") else None,
                    avg_heart_rate=int(act["average_heartrate"]) if act.get("has_heartrate") and act.get("average_heartrate") else None,
                    max_heart_rate=int(act["max_heartrate"]) if act.get("has_heartrate") and act.get("max_heartrate") else None,
                    avg_pace=avg_pace,
                    avg_speed=avg_speed_kph,
                    elevation_gain=act.get("total_elevation_gain"),
                )
                db.add(record)
                synced += 1
            except Exception as e:
                errors.append(f"Activity {act.get('id', '?')}: {e}")
                logger.warning("Failed to process strava activity: %s", e)

        if synced > 0:
            db.commit()

        db_update2 = SessionLocal()
        try:
            conn = db_update2.query(WatchConnection).get(connection.id)
            if conn:
                conn.last_sync_at = datetime.now()
                conn.status = "active"
                conn.error_message = None
                db_update2.commit()
        finally:
            db_update2.close()

    except Exception as e:
        logger.error("Strava sync failed: %s", e)
        db_err = SessionLocal()
        try:
            conn = db_err.query(WatchConnection).get(connection.id)
            if conn:
                conn.status = "error"
                conn.error_message = str(e)[:500]
                db_err.commit()
        finally:
            db_err.close()
        raise
    finally:
        db.close()

    return {"source": "strava", "synced": synced, "errors": errors}


def handle_strava_webhook(event: dict) -> None:
    if event.get("object_type") != "activity" or event.get("aspect_type") != "create":
        return

    db = SessionLocal()
    try:
        strava_conns = db.query(WatchConnection).filter(
            WatchConnection.source == "strava",
            WatchConnection.status == "active",
        ).all()

        for conn in strava_conns:
            creds = json.loads(conn.credentials)
            athlete_id = creds.get("athlete_id")
            if str(athlete_id) == str(event.get("owner_id")):
                sync_strava_activities(conn, days=1)
                break
    finally:
        db.close()
