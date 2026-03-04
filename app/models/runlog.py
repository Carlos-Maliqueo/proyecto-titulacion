from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.db.base_class import Base

class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)

    job = Column(String(50), nullable=False)        # ej: 'etl_daily' | 'manual_parse'
    source = Column(String(50), nullable=True)      # ej: 'gosocket'

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="RUNNING") # RUNNING|OK|ERROR|PARTIAL

    files_total = Column(Integer, nullable=False, default=0)
    files_ok = Column(Integer, nullable=False, default=0)
    files_failed = Column(Integer, nullable=False, default=0)

    headers_inserted = Column(Integer, nullable=False, default=0)
    details_inserted = Column(Integer, nullable=False, default=0)
    dq_violations = Column(Integer, nullable=False, default=0)

    errors = Column(JSONB, nullable=True)  # lista/detalle de errores por archivo o globales
    note = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_run_logs_started_at", "started_at"),
        Index("ix_run_logs_status", "status"),
        Index("ix_run_logs_job", "job"),
    )
