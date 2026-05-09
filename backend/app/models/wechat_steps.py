from sqlalchemy import Column, Date, DateTime, Integer, func

from app.database import Base


class WechatStep(Base):
    __tablename__ = "wechat_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    steps = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.now())
