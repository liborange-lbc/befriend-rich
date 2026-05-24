from datetime import datetime

from pydantic import BaseModel


class GarminConnectRequest(BaseModel):
    email: str
    password: str


class CorosConnectRequest(BaseModel):
    email: str
    password: str
    region: str = "cn"  # cn | eu | us


class StravaCallbackRequest(BaseModel):
    code: str


class ActivityOut(BaseModel):
    id: int
    source: str
    source_id: str
    sport_type: str
    name: str
    start_time: datetime
    duration_seconds: int
    distance_meters: float | None = None
    calories: int | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_pace: float | None = None
    avg_speed: float | None = None
    elevation_gain: float | None = None


class ConnectionOut(BaseModel):
    id: int
    source: str
    status: str
    last_sync_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class SyncResult(BaseModel):
    source: str
    synced: int
    errors: list[str] = []
