from sqlalchemy import Column, Float, ForeignKey, Integer, UniqueConstraint

from app.database import Base


class RebalanceTarget(Base):
    __tablename__ = "rebalance_targets"
    __table_args__ = (
        UniqueConstraint("model_id", "category_id", name="uq_rebalance_model_cat"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("class_models.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("class_categories.id", ondelete="CASCADE"), nullable=False, index=True)
    target_pct = Column(Float, nullable=False, default=0.0)
