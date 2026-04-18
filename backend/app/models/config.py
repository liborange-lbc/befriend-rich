from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False, default="")
    category = Column(String(50), nullable=False, default="general")
    description = Column(String(200), nullable=False, default="")
