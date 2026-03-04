"""placeholder for container-generated revision e9879d193bfa"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9879d193bfa'
down_revision: Union[str, None] = 'c7cd547e141f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Esta revisión se generó dentro del contenedor y ya está aplicada en la BD.
    # La dejamos como NO-OP para que el repositorio y la BD queden coherentes.
    pass

def downgrade() -> None:
    pass
