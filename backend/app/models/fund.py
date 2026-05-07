from sqlalchemy import Boolean, Column, Float, Integer, String

from app.database import Base


class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    currency = Column(String(10), nullable=False, default="CNY")
    data_source = Column(String(20), nullable=False, default="tushare")
    fee_rate = Column(Float, nullable=False, default=0.0)
    management_fee = Column(Float, nullable=True)  # 管理费率 (%)
    custody_fee = Column(Float, nullable=True)  # 托管费率 (%)
    service_fee = Column(Float, nullable=True)  # 销售服务费率 (%)
    is_active = Column(Boolean, nullable=False, default=True)
    holding_source = Column(String(20), nullable=True)  # 持仓数据来源代码（母ETF/代理基金）
