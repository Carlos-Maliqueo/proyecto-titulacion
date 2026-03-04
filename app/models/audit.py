from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.db.base_class import Base
from sqlalchemy.dialects.postgresql import JSONB

# auditoria de accesos y acciones
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user = Column(String(255), nullable=True)
    path = Column(String(512), nullable=False)
    method = Column(String(10), nullable=False)
    status = Column(Integer, nullable=False)

    #acciones
    action = Column(String(100), nullable=True)       # file_upload, xml_parse
    resource = Column(String(50), nullable=True)      # file, dte_header
    resource_id = Column(Integer, nullable=True)      # id relacionado
    extra = Column(JSONB, nullable=True)              # payload 

    __table_args__ = (
        Index("ix_audit_logs_ts", "ts"),
        Index("ix_audit_logs_user", "user"),
        Index("ix_audit_logs_path", "path"),
    )
