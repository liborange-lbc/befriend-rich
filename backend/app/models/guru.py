from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Guru(Base):
    __tablename__ = "gurus"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100))
    slug = Column(String(100), unique=True, nullable=False)
    category = Column(String(20))  # china_fund / asia / north_america
    description = Column(Text)
    num_holdings = Column(Integer, default=0)
    num_trades = Column(Integer, default=0)

    holdings = relationship("GuruHolding", back_populates="guru", lazy="selectin")
    trades = relationship("GuruTrade", back_populates="guru", lazy="selectin")


class GuruHolding(Base):
    __tablename__ = "guru_holdings"

    id = Column(Integer, primary_key=True)
    guru_id = Column(Integer, ForeignKey("gurus.id"))
    stock_code = Column(String(20))
    stock_name = Column(String(100))
    position_change = Column(String(20))
    trade_impact_pct = Column(String(20))
    shares = Column(String(50))
    value = Column(String(50))
    weight_pct = Column(String(20))
    ownership_pct = Column(String(20))
    sector = Column(String(80))
    market_cap = Column(String(50))
    return_3m_pct = Column(String(20))
    return_ytd_pct = Column(String(20))

    guru = relationship("Guru", back_populates="holdings")


class GuruTrade(Base):
    __tablename__ = "guru_trades"

    id = Column(Integer, primary_key=True)
    guru_id = Column(Integer, ForeignKey("gurus.id"))
    stock_code = Column(String(20))
    stock_name = Column(String(100))
    action = Column(String(50))
    shares_changed = Column(String(50))
    price = Column(String(50))
    value = Column(String(50))
    trade_date = Column(String(20))
    report_date = Column(String(20))
    current_shares = Column(String(50))

    guru = relationship("Guru", back_populates="trades")


class GuruStock(Base):
    __tablename__ = "guru_stocks"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True)
    name = Column(String(100))
    market = Column(String(10))  # A / HK / US / TW
    sector = Column(String(80))
    guru_count = Column(Integer, default=0)
