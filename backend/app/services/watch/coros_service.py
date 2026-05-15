"""COROS Training Hub API client for syncing activity data.

Uses the unofficial COROS Team API (same endpoints used by coros-mcp projects).
Regional base URLs:
  - China:    https://teamcnapi.coros.com
  - Europe:   https://teameuapi.coros.com
  - Americas: https://teamapi.coros.com
"""

import json
import logging
from datetime import datetime, timedelta

import httpx

from app.database import SessionLocal
from app.models.exercise import ExerciseRecord
from app.models.watch import WatchConnection

logger = logging.getLogger(__name__)

_REGION_BASE_URLS = {
    "cn": "https://teamcnapi.coros.com",
    "eu": "https://teameuapi.coros.com",
    "us": "https://teamapi.coros.com",
}

# COROS sport_type ID → normalized sport_type
_SPORT_MAP = {
    100: "run",       # Outdoor Run
    101: "run",       # Indoor Run
    102: "run",       # Trail Run
    103: "run",       # Track Run
    200: "ride",      # Road Bike
    201: "ride",      # Indoor Bike
    202: "ride",      # Mountain Bike
    203: "ride",      # Gravel Bike
    300: "swim",      # Pool Swim
    301: "swim",      # Open Water Swim
    400: "hike",      # Hike
    401: "walk",      # Walk
    500: "strength",  # Strength
    501: "strength",  # Gym Cardio
    600: "ski",       # Ski
    601: "snowboard", # Snowboard
    700: "rowing",    # Rowing
    800: "yoga",      # Yoga
    10000: "other",   # Multisport
}


def _normalize_sport(sport_type_id: int) -> str:
    return _SPORT_MAP.get(sport_type_id, "other")


def _get_base_url(region: str) -> str:
    return _REGION_BASE_URLS.get(region, _REGION_BASE_URLS["cn"])


def test_coros_login(email: str, password: str, region: str = "cn") -> dict:
    """Test COROS login and return user info + access token."""
    base_url = _get_base_url(region)
    resp = httpx.post(
        f"{base_url}/account/login",
        json={"account": email, "accountType": 2, "pwd": password},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("result") != "0000" and data.get("apiCode") != "0000":
        raise ValueError(data.get("message", "登录失败"))

    user_info = data.get("data", {})
    return {
        "access_token": user_info.get("accessToken", ""),
        "user_id": user_info.get("userId", ""),
        "nickname": user_info.get("nickname", email),
    }


def _get_auth_headers(connection: WatchConnection) -> tuple[str, dict]:
    """Return (base_url, headers) from stored credentials."""
    creds = json.loads(connection.credentials)
    region = creds.get("region", "cn")
    base_url = _get_base_url(region)

    access_token = creds.get("access_token", "")
    if not access_token:
        # Re-login to get fresh token
        result = test_coros_login(creds["email"], creds["password"], region)
        access_token = result["access_token"]
        # Persist new token
        creds["access_token"] = access_token
        _update_credentials(connection.id, creds)

    headers = {
        "accessToken": access_token,
        "Content-Type": "application/json",
    }
    return base_url, headers


def _update_credentials(conn_id: int, creds: dict):
    db = SessionLocal()
    try:
        conn = db.query(WatchConnection).get(conn_id)
        if conn:
            conn.credentials = json.dumps(creds)
            db.commit()
    finally:
        db.close()


def sync_coros_activities(connection: WatchConnection, days: int = 7) -> dict:
    """Fetch activities from COROS and upsert into ExerciseRecord."""
    openid = connection.openid
    base_url, headers = _get_auth_headers(connection)

    # Query activities for the date range
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    resp = httpx.get(
        f"{base_url}/activity/query",
        headers=headers,
        params={"size": 100, "pageNumber": 1, "startDate": start_date, "endDate": end_date},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("result") != "0000" and data.get("apiCode") != "0000":
        msg = data.get("message", "获取活动列表失败")
        # Token expired — re-login and retry once
        if "token" in msg.lower() or "auth" in msg.lower() or data.get("apiCode") == "0003":
            creds = json.loads(connection.credentials)
            result = test_coros_login(creds["email"], creds["password"], creds.get("region", "cn"))
            creds["access_token"] = result["access_token"]
            _update_credentials(connection.id, creds)
            headers["accessToken"] = creds["access_token"]
            resp = httpx.get(
                f"{base_url}/activity/query",
                headers=headers,
                params={"size": 100, "pageNumber": 1, "startDate": start_date, "endDate": end_date},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("result") != "0000" and data.get("apiCode") != "0000":
            raise ValueError(data.get("message", "获取活动列表失败"))

    activities = data.get("data", {}).get("dataList", [])
    synced = 0
    errors = []

    db = SessionLocal()
    try:
        for act in activities:
            try:
                source_id = str(act.get("labelId", ""))
                if not source_id:
                    continue

                existing = db.query(ExerciseRecord).filter(
                    ExerciseRecord.source == "coros",
                    ExerciseRecord.source_id == source_id,
                ).first()
                if existing:
                    continue

                # Parse start time (epoch seconds or date string)
                start_ts = act.get("startTime")
                if isinstance(start_ts, (int, float)) and start_ts > 0:
                    start_time = datetime.fromtimestamp(start_ts)
                else:
                    start_time = datetime.now()

                sport_type_id = act.get("sportType", 0)
                duration = act.get("duration", 0) or act.get("totalTime", 0) or 0
                distance = act.get("distance", None)
                if distance:
                    distance = round(float(distance), 1)

                avg_speed_mps = act.get("avgSpeed")
                avg_pace = None
                avg_speed_kph = None
                if avg_speed_mps and float(avg_speed_mps) > 0:
                    avg_speed_mps = float(avg_speed_mps)
                    avg_speed_kph = round(avg_speed_mps * 3.6, 2)
                    avg_pace = round(1000.0 / avg_speed_mps, 1)

                record = ExerciseRecord(
                    openid=openid,
                    source="coros",
                    source_id=source_id,
                    sport_type=_normalize_sport(sport_type_id),
                    name=act.get("name", "") or act.get("activityName", "") or "",
                    start_time=start_time,
                    duration_seconds=int(duration),
                    distance_meters=distance,
                    calories=act.get("calorie") or act.get("calories"),
                    avg_heart_rate=act.get("avgHr") or act.get("avgHeartRate"),
                    max_heart_rate=act.get("maxHr") or act.get("maxHeartRate"),
                    avg_pace=avg_pace,
                    avg_speed=avg_speed_kph,
                    elevation_gain=act.get("gainElevation") or act.get("totalAscent"),
                    detail_json=json.dumps(act, ensure_ascii=False, default=str),
                )
                db.add(record)
                synced += 1
            except Exception as e:
                errors.append(f"Activity {act.get('labelId', '?')}: {e}")
                logger.warning("Failed to process COROS activity: %s", e)

        if synced > 0:
            db.commit()

        _update_connection_status(connection.id, "active", None)

    except Exception as e:
        logger.error("COROS sync failed: %s", e)
        _update_connection_status(connection.id, "error", str(e)[:500])
        raise
    finally:
        db.close()

    return {"source": "coros", "synced": synced, "errors": errors}


def _update_connection_status(conn_id: int, status: str, error_msg: str | None):
    db = SessionLocal()
    try:
        conn = db.query(WatchConnection).get(conn_id)
        if conn:
            conn.last_sync_at = datetime.now()
            conn.status = status
            conn.error_message = error_msg
            db.commit()
    finally:
        db.close()
