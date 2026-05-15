from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint, func

from app.database import Base


class ExerciseRecord(Base):
    __tablename__ = "exercise_records"
    __table_args__ = (
        UniqueConstraint("openid", "source", "source_id", name="uq_exercise_source"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=False, index=True)
    source = Column(String(20), nullable=False)  # garmin | strava | coros | huawei | xunji | checkin
    source_id = Column(String(100), nullable=True)  # external dedup ID, NULL for checkin
    sport_type = Column(String(50), nullable=False)  # run | ride | swim | hike | walk | strength | baduanjin | taichi | jingang | ...
    name = Column(String(200), nullable=False, default="")
    start_time = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    distance_meters = Column(Float, nullable=True)
    calories = Column(Integer, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    avg_pace = Column(Float, nullable=True)  # seconds per km
    avg_speed = Column(Float, nullable=True)  # km/h
    elevation_gain = Column(Float, nullable=True)  # meters
    detail_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
