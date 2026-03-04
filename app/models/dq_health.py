from sqlalchemy import Column, Date, Integer, Numeric, DateTime, func
from app.db.base_class import Base 

class DqHealth(Base):
    __tablename__ = "dq_health"

    day = Column(Date, primary_key=True)
    violations_total = Column(Integer, nullable=False, default=0)
    headers = Column(Integer, nullable=False, default=0)
    details = Column(Integer, nullable=False, default=0)
    score = Column(Numeric(5, 2), nullable=False, default=100.00)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
