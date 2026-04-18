from sqlalchemy import Column, Date, Float, ForeignKey, Integer, Text, UniqueConstraint

from app.database import Base


class PortfolioRecord(Base):
    __tablename__ = "portfolio_records"
    __table_args__ = (
        UniqueConstraint("fund_id", "record_date", name="uq_portfolio_fund_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True)
    record_date = Column(Date, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    amount_cny = Column(Float, nullable=False)
    profit = Column(Float, nullable=True, default=0.0)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False, unique=True, index=True)
    total_amount_cny = Column(Float, nullable=False)
    model_breakdown = Column(Text, nullable=False, default="{}")
