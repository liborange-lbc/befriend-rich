from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from app.database import Base


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_date = Column(Date, nullable=False, index=True)
    source = Column(String(20), nullable=False)
    file_name = Column(String(200), nullable=False)
    record_count = Column(Integer, nullable=False, default=0)
    new_funds_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
