"""add_etl_scheduler_dq_audit

Revision ID: 03e377b98230
Revises: 836c0ac06aef
Create Date: 2025-10-14 18:09:48.427880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '03e377b98230'
down_revision: Union[str, None] = '836c0ac06aef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "etl_state",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        comment="Key-Value para watermarks (p.ej. last_fch_emis, last_id)"
    )

    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
        sa.Column("source", sa.String(50), nullable=False),  # 'gosocket' | 'manual'
        sa.Column("rows_in", sa.Integer),
        sa.Column("rows_out", sa.Integer),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("ix_run_logs_started_at", "run_logs", ["started_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("action", sa.String(50), nullable=False),   # 'login','upload','parse','view','export'
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("ip", sa.String(45)),
        sa.Column("extra", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index("ix_audit_logs_ts", "audit_logs", ["ts"])

    op.create_table(
        "dq_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),  # 'WARN'|'ERROR'
        sa.Column("entity", sa.String(10), nullable=False), # 'header'|'detail'
    )

    op.create_table(
        "dq_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("dq_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("passed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("uq_dq_results", "dq_results", ["run_id", "rule_id"], unique=True)

    op.create_table(
        "dq_violations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("dq_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity", sa.String(10), nullable=False),  # 'header'|'detail'
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("message", sa.String(255), nullable=False),
    )

def downgrade():
    op.drop_table("dq_violations")
    op.drop_index("uq_dq_results", table_name="dq_results")
    op.drop_table("dq_results")
    op.drop_table("dq_rules")
    op.drop_index("ix_audit_logs_ts", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_run_logs_started_at", table_name="run_logs")
    op.drop_table("run_logs")
    op.drop_table("etl_state")