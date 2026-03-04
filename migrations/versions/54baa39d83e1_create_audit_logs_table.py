"""create audit_logs table

Revision ID: 54baa39d83e1
Revises: 5deac3bdd8c7
Create Date: 2025-10-18 19:19:18.639226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '54baa39d83e1'
down_revision: Union[str, None] = '5deac3bdd8c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user", sa.String(length=255), nullable=True),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("resource", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_audit_logs_ts", "audit_logs", ["ts"])
    op.create_index("ix_audit_logs_user", "audit_logs", ["user"])
    op.create_index("ix_audit_logs_path", "audit_logs", ["path"])

def downgrade():
    op.drop_index("ix_audit_logs_path", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user", table_name="audit_logs")
    op.drop_index("ix_audit_logs_ts", table_name="audit_logs")
    op.drop_table("audit_logs")
