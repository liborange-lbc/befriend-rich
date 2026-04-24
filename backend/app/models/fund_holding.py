from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class FundHolding(Base):
    __tablename__ = "fund_holdings"
    __table_args__ = (
        UniqueConstraint("fund_id", "quarter", "stock_code", name="uq_fund_quarter_stock"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False, index=True)
    quarter = Column(String(20), nullable=False, index=True)  # e.g. "2024Q4"
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100), nullable=False)
    holding_ratio = Column(Float, nullable=True)  # 占净值比例 (%)
    holding_shares = Column(Float, nullable=True)  # 持仓股数 (万股)
    holding_value = Column(Float, nullable=True)  # 持仓市值 (万元)
    disclosure_date = Column(String(30), nullable=True)  # e.g. "2024年4季度报告"
