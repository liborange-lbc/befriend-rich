from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func

from app.database import Base


class WatchConnection(Base):
    __tablename__ = "watch_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    source = Column(String(20), nullable=False)  # 'garmin' | 'strava'
    status = Column(String(20), nullable=False, default="active")  # 'active' | 'inactive' | 'error'
    credentials = Column(Text, nullable=False, default="{}")  # JSON: garmin={email,password}, strava={access_token,refresh_token,expires_at,athlete_id}
    last_sync_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class WatchActivity(Base):
    __tablename__ = "watch_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    source = Column(String(20), nullable=False)  # 'garmin' | 'coros' | 'huawei'
    source_id = Column(String(100), nullable=False)  # external ID for dedup
    sport_type = Column(String(50), nullable=False)  # 'run' | 'ride' | 'swim' | 'hike' | 'walk' | ...
    name = Column(String(200), nullable=False, default="")
    start_time = Column(DateTime, nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=0)
    distance_meters = Column(Float, nullable=True)
    calories = Column(Integer, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    avg_pace = Column(Float, nullable=True)  # seconds per km (for run/hike)
    avg_speed = Column(Float, nullable=True)  # km/h (for ride)
    elevation_gain = Column(Float, nullable=True)  # meters
    created_at = Column(DateTime, default=func.now())
