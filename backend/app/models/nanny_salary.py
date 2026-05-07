from sqlalchemy import Column, Date, Integer, String, Text

from app.database import Base


class NannySalaryConfig(Base):
    __tablename__ = "nanny_salary_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    salary_amount = Column(Integer, nullable=False, default=9000)
    cycle_days = Column(Integer, nullable=False, default=26)


class NannySalaryHoliday(Base):
    __tablename__ = "nanny_salary_holidays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    extra_days = Column(Integer, nullable=False, default=0)


class NannySalaryLeave(Base):
    __tablename__ = "nanny_salary_leaves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(200), nullable=False, default="")
