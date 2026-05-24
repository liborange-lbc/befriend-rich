import logging

from app.database import SessionLocal
from app.models.watch import WatchConnection
from app.services.watch.coros_service import sync_coros_activities
from app.services.watch.garmin_service import sync_garmin_activities, sync_garmin_daily_health
from app.services.watch.strava_service import sync_strava_activities

logger = logging.getLogger(__name__)


def sync_all_connections(days: int = 2, openid: str | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        query = db.query(WatchConnection).filter(
            WatchConnection.status.in_(["active", "error"]),
        )
        if openid:
            query = query.filter(WatchConnection.openid == openid)
        connections = query.all()
    finally:
        db.close()

    results = []
    for conn in connections:
        try:
            if conn.source == "garmin":
                result = sync_garmin_activities(conn, days=days)
                # Also sync daily health data
                try:
                    health_days = min(days, 30)  # cap daily health to 30 days
                    health_result = sync_garmin_daily_health(conn, days=health_days)
                    result["health_synced"] = health_result["synced_days"]
                except Exception as he:
                    logger.warning("Garmin daily health sync failed: %s", he)
                    result["health_synced"] = 0
            elif conn.source == "strava":
                result = sync_strava_activities(conn, days=days)
            elif conn.source == "coros":
                result = sync_coros_activities(conn, days=days)
            else:
                continue
            results.append(result)
            logger.info("Synced %s: %d activities", conn.source, result["synced"])
        except Exception as e:
            logger.error("Failed to sync connection %d (%s): %s", conn.id, conn.source, e)
            results.append({"source": conn.source, "synced": 0, "errors": [str(e)]})

    return results
