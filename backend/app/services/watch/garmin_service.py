import json
import logging
import os
from datetime import date, datetime, timedelta

from garminconnect import Garmin

from app.database import SessionLocal
from app.models.watch import GarminDailySummary, WatchActivity, WatchConnection

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


def _safe_int(val):
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_garmin_client(connection: WatchConnection) -> Garmin:
    creds = json.loads(connection.credentials)
    os.makedirs(TOKENSTORE_DIR, exist_ok=True)
    tokenstore_path = os.path.join(TOKENSTORE_DIR, "tokens")
    client = Garmin(creds.get("email", ""), creds.get("password", ""))
    client.login(tokenstore_path)
    return client


def test_garmin_login(email: str, password: str) -> dict:
    os.makedirs(TOKENSTORE_DIR, exist_ok=True)
    tokenstore_path = os.path.join(TOKENSTORE_DIR, "tokens")
    client = Garmin(email, password)
    client.login(tokenstore_path)
    display_name = client.get_full_name() or email
    return {"display_name": display_name}


def sync_garmin_activities(connection: WatchConnection, days: int = 2) -> dict:
    openid = connection.openid
    client = _get_garmin_client(connection)

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
                    # Backfill detail_json if missing
                    if not existing.detail_json:
                        existing.detail_json = json.dumps(act, ensure_ascii=False, default=str)
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
                    detail_json=json.dumps(act, ensure_ascii=False, default=str),
                )
                db.add(record)
                synced += 1
            except Exception as e:
                errors.append(f"Activity {act.get('activityId', '?')}: {e}")
                logger.warning("Failed to process garmin activity: %s", e)

        if synced > 0:
            db.commit()

        _update_connection_status(connection.id, "active", None)

    except Exception as e:
        logger.error("Garmin sync failed: %s", e)
        _update_connection_status(connection.id, "error", str(e)[:500])
        raise
    finally:
        db.close()

    return {"source": "garmin", "synced": synced, "errors": errors}


def sync_garmin_daily_health(connection: WatchConnection, days: int = 7) -> dict:
    """Sync daily health data: sleep, HR, stress, body battery, SpO2, respiration."""
    openid = connection.openid
    client = _get_garmin_client(connection)

    synced = 0
    errors = []
    db = SessionLocal()

    try:
        for i in range(days):
            cdate_obj = date.today() - timedelta(days=i)
            cdate = cdate_obj.isoformat()
            try:
                # Check if already synced (skip today for incomplete data)
                existing = db.query(GarminDailySummary).filter(
                    GarminDailySummary.date == cdate_obj,
                    GarminDailySummary.openid == openid,
                ).first()
                # Re-sync today and yesterday (data may be incomplete), skip older
                if existing and i >= 2:
                    continue

                # Fetch all available daily data
                raw = {}
                try:
                    raw["summary"] = client.get_user_summary(cdate)
                except Exception:
                    pass
                try:
                    raw["sleep"] = client.get_sleep_data(cdate)
                except Exception:
                    pass
                try:
                    raw["heart_rates"] = client.get_heart_rates(cdate)
                except Exception:
                    pass
                try:
                    raw["stress"] = client.get_all_day_stress(cdate)
                except Exception:
                    pass
                try:
                    raw["body_battery"] = client.get_body_battery(cdate, cdate)
                except Exception:
                    pass
                try:
                    raw["spo2"] = client.get_spo2_data(cdate)
                except Exception:
                    pass
                try:
                    raw["respiration"] = client.get_respiration_data(cdate)
                except Exception:
                    pass

                summary = raw.get("summary") or {}
                sleep = raw.get("sleep") or {}
                hr = raw.get("heart_rates") or {}
                stress_data = raw.get("stress") or {}
                bb = raw.get("body_battery") or {}

                # Extract sleep details
                sleep_daily = sleep.get("dailySleepDTO") or {}
                sleep_levels = sleep_daily.get("sleepLevels") or sleep.get("sleepLevels") or {}

                # Extract stress
                stress_values = []
                for entry in (stress_data.get("stressValuesArray") or stress_data.get("bodyStressDataList") or []):
                    if isinstance(entry, list) and len(entry) >= 2 and entry[1] is not None and entry[1] > 0:
                        stress_values.append(entry[1])
                    elif isinstance(entry, dict) and entry.get("stressLevel"):
                        stress_values.append(entry["stressLevel"])

                # Extract body battery (can be list of dicts or nested structure)
                bb_high = None
                bb_low = None
                if isinstance(bb, list):
                    for item in bb:
                        if isinstance(item, dict):
                            val = item.get("bodyBatteryLevel") or item.get("charged")
                            if val is not None:
                                if bb_high is None or val > bb_high:
                                    bb_high = val
                                if bb_low is None or val < bb_low:
                                    bb_low = val

                # Build record
                fields = {
                    "openid": openid,
                    "date": cdate_obj,
                    "steps": _safe_int(summary.get("totalSteps")),
                    "floors_climbed": _safe_int(summary.get("floorsAscended")),
                    "active_minutes": _safe_int(summary.get("activeSeconds") and summary["activeSeconds"] // 60),
                    "intensity_minutes": _safe_int(summary.get("intensityMinutes") or summary.get("moderateIntensityMinutes", 0)),
                    "calories_total": _safe_int(summary.get("totalKilocalories")),
                    "distance_meters": _safe_float(summary.get("totalDistanceMeters")),
                    "resting_hr": _safe_int(hr.get("restingHeartRate") or summary.get("restingHeartRate")),
                    "min_hr": _safe_int(hr.get("minHeartRate")),
                    "max_hr": _safe_int(hr.get("maxHeartRate")),
                    "body_battery_high": _safe_int(summary.get("bodyBatteryHighestValue") or bb_high),
                    "body_battery_low": _safe_int(summary.get("bodyBatteryLowestValue") or bb_low),
                    "avg_stress": _safe_int(summary.get("averageStressLevel") or (sum(stress_values) // len(stress_values) if stress_values else None)),
                    "max_stress": _safe_int(summary.get("maxStressLevel") or (max(stress_values) if stress_values else None)),
                    "sleep_score": _safe_int(sleep_daily.get("sleepScores", {}).get("overall", {}).get("value") if isinstance(sleep_daily.get("sleepScores"), dict) else None),
                    "sleep_start": sleep_daily.get("sleepStartTimestampLocal") or sleep_daily.get("sleepStart"),
                    "sleep_end": sleep_daily.get("sleepEndTimestampLocal") or sleep_daily.get("sleepEnd"),
                    "sleep_duration_seconds": _safe_int(sleep_daily.get("sleepTimeInSeconds")),
                    "deep_sleep_seconds": _safe_int(sleep_daily.get("deepSleepSeconds") or sleep_levels.get("deepSleepSeconds")),
                    "light_sleep_seconds": _safe_int(sleep_daily.get("lightSleepSeconds") or sleep_levels.get("lightSleepSeconds")),
                    "rem_sleep_seconds": _safe_int(sleep_daily.get("remSleepSeconds") or sleep_levels.get("remSleepSeconds")),
                    "awake_seconds": _safe_int(sleep_daily.get("awakeSleepSeconds") or sleep_levels.get("awakeSleepSeconds")),
                    "avg_spo2": _safe_float(summary.get("averageSpo2")),
                    "avg_respiration": _safe_float(summary.get("averageRespirationValue")),
                    "detail_json": json.dumps(raw, ensure_ascii=False, default=str),
                }

                if existing:
                    for k, v in fields.items():
                        if k not in ("openid", "date"):
                            setattr(existing, k, v)
                else:
                    db.add(GarminDailySummary(**fields))
                synced += 1

            except Exception as e:
                errors.append(f"Date {cdate}: {e}")
                logger.warning("Failed to sync garmin daily data for %s: %s", cdate, e)

        db.commit()
    except Exception as e:
        logger.error("Garmin daily health sync failed: %s", e)
        raise
    finally:
        db.close()

    return {"synced_days": synced, "errors": errors}


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
