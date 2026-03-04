from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.db.base_class import Base

class DqRule(Base):
    __tablename__ = "dq_rules"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    level = Column(String(10), nullable=False)   # error o warn
    entity = Column(String(20), nullable=False)  # header o detail

class DqViolation(Base):
    __tablename__ = "dq_violations"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), nullable=True)
    rule_id = Column(Integer, ForeignKey("dq_rules.id", ondelete="RESTRICT"), nullable=False, index=True)
    entity = Column(String(20), nullable=False)   # header o detail
    entity_id = Column(Integer, nullable=False)   # id del header o detail
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_dq_violations_entity_entity_id", "entity", "entity_id"),
        Index("ix_dq_violations_rule_id", "rule_id"),
        Index("ix_dq_violations_run_id", "run_id"),
    )
