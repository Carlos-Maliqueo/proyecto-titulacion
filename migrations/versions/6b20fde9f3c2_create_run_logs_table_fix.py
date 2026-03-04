"""create run_logs table (fix)

Revision ID: 6b20fde9f3c2
Revises: 85e34a613897
Create Date: 2025-10-21 15:18:36.563508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '6b20fde9f3c2'
down_revision: Union[str, None] = '85e34a613897'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("job", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RUNNING"),
        sa.Column("files_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("headers_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dq_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", JSONB, nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("run_id", name="uq_run_logs_run_id"),
    )
    op.create_index("ix_run_logs_started_at", "run_logs", ["started_at"], unique=False)
    op.create_index("ix_run_logs_status", "run_logs", ["status"], unique=False)
    op.create_index("ix_run_logs_job", "run_logs", ["job"], unique=False)

def downgrade():
    op.drop_index("ix_run_logs_job", table_name="run_logs")
    op.drop_index("ix_run_logs_status", table_name="run_logs")
    op.drop_index("ix_run_logs_started_at", table_name="run_logs")
    op.drop_table("run_logs")
