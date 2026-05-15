from sqlalchemy import Column, Date, DateTime, Integer, String, func

from app.database import Base


class BaduanjinRecord(Base):
    __tablename__ = "baduanjin_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    exercise_type = Column(String(32), nullable=False, default="baduanjin")
    duration_seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())
