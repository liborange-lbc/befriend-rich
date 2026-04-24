"""大盘洞察数据模型 — A股市值快照 + 指数成分股"""

from sqlalchemy import Column, Date, Float, Integer, String

from app.database import Base


class MarketStock(Base):
    """A股市值快照，每周刷新"""
    __tablename__ = "market_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    exchange = Column(Integer, nullable=False)  # 1=SH, 0=SZ/BJ
    market_cap = Column(Float, nullable=False)  # 单位：元
    industry = Column(String(50), nullable=True)  # 一级行业
    snapshot_date = Column(Date, nullable=False, index=True)


class MarketIndexComponent(Base):
    """指数成分股，每周刷新"""
    __tablename__ = "market_index_component"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_code = Column(String(10), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False)
    snapshot_date = Column(Date, nullable=False, index=True)
