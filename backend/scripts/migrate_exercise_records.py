"""
Migrate data from wechat_watch_activities, baduanjin_records, xunji_train_cache
into the unified exercise_records table.

Usage: cd backend && python -m scripts.migrate_exercise_records
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

from app.database import SessionLocal, engine, Base
from app.models.exercise import ExerciseRecord  # noqa: ensure table exists


def migrate():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        _migrate_watch_activities(db)
        _migrate_baduanjin(db)
        _migrate_xunji(db)
        print("\nMigration complete.")
    finally:
        db.close()


def _migrate_watch_activities(db):
    """Migrate from wechat_watch_activities → exercise_records."""
    from sqlalchemy import text

    rows = db.execute(text(
        "SELECT id, openid, source, source_id, sport_type, name, "
        "start_time, duration_seconds, distance_meters, calories, "
        "avg_heart_rate, max_heart_rate, avg_pace, avg_speed, "
        "elevation_gain, detail_json, created_at "
        "FROM wechat_watch_activities"
    )).fetchall()

    count = 0
    skipped = 0
    for r in rows:
        # Check dedup
        exists = db.query(ExerciseRecord).filter(
            ExerciseRecord.openid == r[1],
            ExerciseRecord.source == r[2],
            ExerciseRecord.source_id == r[3],
        ).first()
        if exists:
            skipped += 1
            continue

        record = ExerciseRecord(
            openid=r[1],
            source=r[2],
            source_id=r[3],
            sport_type=r[4],
            name=r[5] or "",
            start_time=r[6],
            duration_seconds=r[7] or 0,
            distance_meters=r[8],
            calories=r[9],
            avg_heart_rate=r[10],
            max_heart_rate=r[11],
            avg_pace=r[12],
            avg_speed=r[13],
            elevation_gain=r[14],
            detail_json=r[15],
        )
        db.add(record)
        count += 1

    db.commit()
    print(f"[watch_activities] migrated: {count}, skipped: {skipped}")


def _migrate_baduanjin(db):
    """Migrate from baduanjin_records → exercise_records."""
    from sqlalchemy import text

    rows = db.execute(text(
        "SELECT id, openid, date, exercise_type, duration_seconds, created_at "
        "FROM baduanjin_records"
    )).fetchall()

    sport_labels = {
        "baduanjin": "八段锦",
        "jingang": "金刚功",
        "taichi": "太极",
    }

    count = 0
    for r in rows:
        # Use created_at as start_time for more precise time; fallback to date noon
        start_time = r[5] if r[5] else datetime.strptime(str(r[2]), "%Y-%m-%d").replace(hour=12)
        sport_type = r[3] or "baduanjin"

        record = ExerciseRecord(
            openid=r[1],
            source="checkin",
            source_id=None,
            sport_type=sport_type,
            name=sport_labels.get(sport_type, sport_type),
            start_time=start_time,
            duration_seconds=r[4] or 0,
        )
        db.add(record)
        count += 1

    db.commit()
    print(f"[baduanjin_records] migrated: {count}")


def _migrate_xunji(db):
    """Migrate from xunji_train_cache → exercise_records."""
    from sqlalchemy import text

    rows = db.execute(text(
        "SELECT openid, date, raw_json FROM xunji_train_cache"
    )).fetchall()

    count = 0
    errors = 0
    for r in rows:
        openid = r[0]
        datestr = r[1]
        try:
            records = json.loads(r[2])
        except Exception:
            errors += 1
            continue

        for rec in records:
            parts = rec.split(",") if isinstance(rec, str) else []
            name = parts[2] if len(parts) > 2 else "训练"
            start_time = None
            dur = 0
            source_id = None

            for p in parts:
                if p.startswith("train_time:"):
                    times = p[11:].split("-")
                    if len(times) == 2:
                        try:
                            start_ts = int(times[0])
                            end_ts = int(times[1])
                            start_time = datetime.fromtimestamp(start_ts / 1000)
                            dur = round((end_ts - start_ts) / 1000)
                        except (ValueError, OSError):
                            pass
                elif p.startswith("id:"):
                    source_id = p[3:]

            if not start_time:
                try:
                    start_time = datetime.strptime(datestr, "%Y-%m-%d").replace(hour=8)
                except ValueError:
                    errors += 1
                    continue

            # Map name to sport_type
            sport_type = "strength"
            name_lower = name.lower()
            if "八段锦" in name:
                sport_type = "baduanjin"
            elif "太极" in name:
                sport_type = "taichi"
            elif "金刚" in name:
                sport_type = "jingang"

            # Dedup by source_id
            if source_id:
                exists = db.query(ExerciseRecord).filter(
                    ExerciseRecord.openid == openid,
                    ExerciseRecord.source == "xunji",
                    ExerciseRecord.source_id == source_id,
                ).first()
                if exists:
                    continue

            record = ExerciseRecord(
                openid=openid,
                source="xunji",
                source_id=source_id,
                sport_type=sport_type,
                name=name,
                start_time=start_time,
                duration_seconds=dur,
                detail_json=rec if isinstance(rec, str) else json.dumps(rec, ensure_ascii=False),
            )
            db.add(record)
            count += 1

    db.commit()
    print(f"[xunji_train_cache] migrated: {count}, errors: {errors}")


if __name__ == "__main__":
    migrate()
