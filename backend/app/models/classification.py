from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ClassModel(Base):
    __tablename__ = "class_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, default="")

    categories = relationship(
        "ClassCategory", back_populates="model", cascade="all, delete-orphan"
    )


class ClassCategory(Base):
    __tablename__ = "class_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("class_models.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("class_categories.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False, default=1)
    sort_order = Column(Integer, nullable=False, default=0)

    model = relationship("ClassModel", back_populates="categories")
    children = relationship(
        "ClassCategory",
        backref="parent",
        remote_side=[id],
        foreign_keys=[parent_id],
        cascade="all, delete-orphan",
        single_parent=True,
    )


class FundClassMap(Base):
    __tablename__ = "fund_class_maps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("class_categories.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(Integer, ForeignKey("class_models.id", ondelete="CASCADE"), nullable=False)
