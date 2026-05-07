from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, Text

from app.database import Base


class AllocationTarget(Base):
    __tablename__ = "allocation_targets"
    __table_args__ = (
        Index("ix_alloc_target_model_status", "model_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(
        Integer,
        ForeignKey("class_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        Integer,
        ForeignKey("class_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_name = Column(String(100), nullable=False)
    parent_name = Column(String(100), nullable=False)
    target_weight = Column(Float, nullable=False)
    current_weight = Column(Float, nullable=False, default=0.0)
    deviation = Column(Float, nullable=False, default=0.0)
    annual_return = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    calculated_at = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="active")


class AllocationSnapshot(Base):
    __tablename__ = "allocation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(
        Integer,
        ForeignKey("class_models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger = Column(String(50), nullable=False)
    total_capital = Column(Float, nullable=False, default=0.0)
    target_return = Column(Float, nullable=False, default=0.10)
    risk_free_rate = Column(Float, nullable=False, default=0.02)
    backtest_years = Column(Integer, nullable=False, default=5)
    weights_snapshot = Column(Text, nullable=False, default="[]")
    correlation_matrix = Column(Text, nullable=False, default="[]")
    portfolio_expected_return = Column(Float, nullable=True)
    portfolio_volatility = Column(Float, nullable=True)
    portfolio_sharpe = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(String(30), nullable=False)
