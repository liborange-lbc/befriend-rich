from sqlalchemy import Column, Date, Float, Integer, String, UniqueConstraint

from app.database import Base


class USStockVolumeRanking(Base):
    __tablename__ = "us_stock_volume_rankings"
    __table_args__ = (
        UniqueConstraint("date", "ticker", name="uq_us_vol_date_ticker"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    ticker = Column(String(20), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    volume = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
