from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class PortfolioRecord(Base):
    __tablename__ = "wechat_portfolio_records"
    __table_args__ = (
        UniqueConstraint("fund_id", "channel", "record_date", "openid", name="uq_portfolio_fund_channel_date_openid"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True)
    record_date = Column(Date, nullable=False, index=True)  # Always Monday of the ISO week
    amount = Column(Float, nullable=False)
    amount_cny = Column(Float, nullable=False)
    profit = Column(Float, nullable=True)
    weekly_investment = Column(Float, nullable=True)
    channel = Column(String(20), nullable=False, default="微众银行")
    data_date = Column(String(8), nullable=True, index=True)  # yyyyMMdd, actual source date


class PortfolioSnapshot(Base):
    __tablename__ = "wechat_portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "openid", name="uq_snapshot_date_openid"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=True, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    total_amount_cny = Column(Float, nullable=False)
    model_breakdown = Column(Text, nullable=False, default="{}")
