from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from app.database import Base


class DiaryEntry(Base):
    __tablename__ = "diary_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_date = Column(Date, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False, default="")
    mood = Column(String(20), nullable=True)  # bullish / neutral / bearish
    tags = Column(Text, nullable=False, default="[]")  # JSON array of strings
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
