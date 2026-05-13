from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, func

from app.database import Base


class WechatStep(Base):
    __tablename__ = "wechat_steps"
    __table_args__ = (
        UniqueConstraint("date", "openid", name="uq_wechat_steps_date_openid"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    steps = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.now())
