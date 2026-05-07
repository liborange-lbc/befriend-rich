from sqlalchemy import Column, Date, Float, Integer, String, UniqueConstraint

from app.database import Base


class ICOptionPrice(Base):
    __tablename__ = "ic_option_prices"
    __table_args__ = (
        UniqueConstraint("date", "contract_type", name="uq_ic_date_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    contract_type = Column(String(20), nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    contract_code = Column(String(20), nullable=True)
