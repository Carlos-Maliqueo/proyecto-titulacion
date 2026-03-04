"""cast tipo_dte & folio to integer

Revision ID: 836c0ac06aef
Revises: c8a4f2edf326
Create Date: 2025-10-14 14:46:02.313732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '836c0ac06aef'
down_revision: Union[str, None] = 'c8a4f2edf326'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        'dte_headers', 'tipo_dte',
        existing_type=sa.String(),
        type_=sa.Integer(),
        postgresql_using='tipo_dte::integer',
        existing_nullable=False,  # ajusta según tu esquema
        nullable=False
    )
    op.alter_column(
        'dte_headers', 'folio',
        existing_type=sa.String(),
        type_=sa.Integer(),
        postgresql_using='folio::integer',
        existing_nullable=False,  # ajusta según tu esquema
        nullable=False
    )

def downgrade():
    op.alter_column(
        'dte_headers', 'tipo_dte',
        existing_type=sa.Integer(),
        type_=sa.String(),
        postgresql_using='tipo_dte::text',
        nullable=False
    )
    op.alter_column(
        'dte_headers', 'folio',
        existing_type=sa.Integer(),
        type_=sa.String(),
        postgresql_using='folio::text',
        nullable=False
    )
