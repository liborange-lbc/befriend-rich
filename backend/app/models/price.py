from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class FundDailyPrice(Base):
    __tablename__ = "fund_daily_prices"
    __table_args__ = (
        UniqueConstraint("fund_id", "date", name="uq_fund_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    ma_30 = Column(Float, nullable=True)
    ma_60 = Column(Float, nullable=True)
    ma_90 = Column(Float, nullable=True)
    ma_120 = Column(Float, nullable=True)
    ma_180 = Column(Float, nullable=True)
    ma_360 = Column(Float, nullable=True)
    dev_30 = Column(Float, nullable=True)
    dev_60 = Column(Float, nullable=True)
    dev_90 = Column(Float, nullable=True)
    dev_120 = Column(Float, nullable=True)
    dev_180 = Column(Float, nullable=True)
    dev_360 = Column(Float, nullable=True)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("date", "pair", name="uq_rate_date_pair"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    pair = Column(String(10), nullable=False, default="USD/CNY")
    rate = Column(Float, nullable=False)
