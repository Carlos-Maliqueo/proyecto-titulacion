"""ai enrichment on dte_details

Revision ID: 5a3a1e394fb5
Revises: 8b3fdc6f616c
Create Date: 2025-10-30 00:45:07.006775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5a3a1e394fb5'
down_revision: Union[str, None] = '8b3fdc6f616c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column('dte_details', sa.Column('ai_category', sa.String(50), nullable=True))
    op.add_column('dte_details', sa.Column('ai_subcategory', sa.String(60), nullable=True))
    op.add_column('dte_details', sa.Column('ai_brand', sa.String(60), nullable=True))
    op.add_column('dte_details', sa.Column('ai_attrs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('dte_details', sa.Column('ai_confidence', sa.Numeric(5,2), nullable=True))
    op.add_column('dte_details', sa.Column('ai_version', sa.String(20), nullable=True))
    op.create_index('ix_dte_details_ai_category', 'dte_details', ['ai_category'])
    op.create_index('ix_dte_details_ai_subcategory', 'dte_details', ['ai_subcategory'])
    op.create_index('ix_dte_details_ai_brand', 'dte_details', ['ai_brand'])

def downgrade():
    op.drop_index('ix_dte_details_ai_brand', table_name='dte_details')
    op.drop_index('ix_dte_details_ai_subcategory', table_name='dte_details')
    op.drop_index('ix_dte_details_ai_category', table_name='dte_details')
    op.drop_column('dte_details', 'ai_version')
    op.drop_column('dte_details', 'ai_confidence')
    op.drop_column('dte_details', 'ai_attrs')
    op.drop_column('dte_details', 'ai_brand')
    op.drop_column('dte_details', 'ai_subcategory')
    op.drop_column('dte_details', 'ai_category')
