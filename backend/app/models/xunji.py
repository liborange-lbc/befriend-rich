import json

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint, func

from app.database import Base


class XunjiTrainCache(Base):
    __tablename__ = "xunji_train_cache"
    __table_args__ = (
        UniqueConstraint("openid", "date", name="uq_xunji_openid_date"),
    )

    openid = Column(String(64), primary_key=True)
    date = Column(String(10), primary_key=True, index=True)
    raw_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=func.now())

    def get_records(self) -> list[str]:
        try:
            return json.loads(self.raw_json)
        except Exception:
            return []
