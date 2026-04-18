from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String, Text

from app.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="SET NULL"), nullable=True)
    type = Column(String(30), nullable=False, default="dca")
    config = Column(Text, nullable=False, default="{}")
    alert_enabled = Column(Boolean, nullable=False, default=True)
    alert_conditions = Column(Text, nullable=False, default="[]")
    is_active = Column(Boolean, nullable=False, default=True)


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    total_return = Column(Float, nullable=True)
    annual_return = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    profit_loss_ratio = Column(Float, nullable=True)
    trade_log = Column(Text, nullable=False, default="[]")
    equity_curve = Column(Text, nullable=False, default="[]")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="SET NULL"), nullable=True)
    triggered_at = Column(String(30), nullable=False)
    condition_desc = Column(Text, nullable=False, default="")
    current_values = Column(Text, nullable=False, default="{}")
    notified = Column(Boolean, nullable=False, default=False)
