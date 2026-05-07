from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class PortfolioRecord(Base):
    __tablename__ = "portfolio_records"
    __table_args__ = (
        UniqueConstraint("fund_id", "channel", "record_date", name="uq_portfolio_fund_channel_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True)
    record_date = Column(Date, nullable=False, index=True)  # Always Monday of the ISO week
    amount = Column(Float, nullable=False)
    amount_cny = Column(Float, nullable=False)
    profit = Column(Float, nullable=True)
    weekly_investment = Column(Float, nullable=True)
    channel = Column(String(20), nullable=False, default="微众银行")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, unique=True, index=True)
    total_amount_cny = Column(Float, nullable=False)
    model_breakdown = Column(Text, nullable=False, default="{}")
