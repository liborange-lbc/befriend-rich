from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func

from app.database import Base


class WatchConnection(Base):
    __tablename__ = "wechat_watch_connections"

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
    __tablename__ = "wechat_watch_activities"

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
    detail_json = Column(Text, nullable=True)  # full raw response from source
    created_at = Column(DateTime, default=func.now())


class GarminDailySummary(Base):
    __tablename__ = "wechat_garmin_daily"
    __table_args__ = (
        UniqueConstraint("date", "openid", name="uq_garmin_daily_date_openid"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)

    # Steps & Activity
    steps = Column(Integer, nullable=True)
    floors_climbed = Column(Integer, nullable=True)
    active_minutes = Column(Integer, nullable=True)
    intensity_minutes = Column(Integer, nullable=True)
    calories_total = Column(Integer, nullable=True)
    distance_meters = Column(Float, nullable=True)

    # Heart Rate
    resting_hr = Column(Integer, nullable=True)
    min_hr = Column(Integer, nullable=True)
    max_hr = Column(Integer, nullable=True)

    # Body Battery
    body_battery_high = Column(Integer, nullable=True)
    body_battery_low = Column(Integer, nullable=True)

    # Stress
    avg_stress = Column(Integer, nullable=True)
    max_stress = Column(Integer, nullable=True)

    # Sleep
    sleep_score = Column(Integer, nullable=True)
    sleep_start = Column(String(30), nullable=True)
    sleep_end = Column(String(30), nullable=True)
    sleep_duration_seconds = Column(Integer, nullable=True)
    deep_sleep_seconds = Column(Integer, nullable=True)
    light_sleep_seconds = Column(Integer, nullable=True)
    rem_sleep_seconds = Column(Integer, nullable=True)
    awake_seconds = Column(Integer, nullable=True)

    # SpO2 & Respiration
    avg_spo2 = Column(Float, nullable=True)
    avg_respiration = Column(Float, nullable=True)

    # Raw data
    detail_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now())
