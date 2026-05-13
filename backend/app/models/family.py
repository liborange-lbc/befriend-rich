from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class FamilyProfile(Base):
    __tablename__ = "wechat_family_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    avatar_url = Column(String(500), nullable=True)
    nickname = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class InjuryRecord(Base):
    __tablename__ = "wechat_injury_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    who = Column(String(50), nullable=False, default="自己")
    title = Column(String(200), nullable=False)
    start_date = Column(String(20), nullable=False)
    end_date = Column(String(20), nullable=True, default="")
    symptoms = Column(Text, nullable=True, default="")
    treatment = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
