import logging

from app.database import SessionLocal
from app.models.watch import WatchConnection
from app.services.watch.garmin_service import sync_garmin_activities
from app.services.watch.strava_service import sync_strava_activities

logger = logging.getLogger(__name__)


def sync_all_connections(days: int = 2) -> list[dict]:
    db = SessionLocal()
    try:
        connections = db.query(WatchConnection).filter(
            WatchConnection.status.in_(["active", "error"]),
        ).all()
    finally:
        db.close()

    results = []
    for conn in connections:
        try:
            if conn.source == "garmin":
                result = sync_garmin_activities(conn, days=days)
            elif conn.source == "strava":
                result = sync_strava_activities(conn, days=days)
            else:
                continue
            results.append(result)
            logger.info("Synced %s: %d activities", conn.source, result["synced"])
        except Exception as e:
            logger.error("Failed to sync connection %d (%s): %s", conn.id, conn.source, e)
            results.append({"source": conn.source, "synced": 0, "errors": [str(e)]})

    return results
