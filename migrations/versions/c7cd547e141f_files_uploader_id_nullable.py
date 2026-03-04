"""files.uploader_id nullable

Revision ID: c7cd547e141f
Revises: 6b20fde9f3c2
Create Date: 2025-10-22 16:45:36.451588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7cd547e141f'
down_revision: Union[str, None] = '6b20fde9f3c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column("files", "uploader_id", existing_type=sa.Integer(), nullable=True)

def downgrade():
    op.alter_column("files", "uploader_id", existing_type=sa.Integer(), nullable=False)
