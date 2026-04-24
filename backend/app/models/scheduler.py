from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class JobRun(Base):
    """定时任务运行记录"""
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # success / failed
    summary = Column(Text, nullable=True)
