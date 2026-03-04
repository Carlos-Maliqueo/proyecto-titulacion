"""curated views

Revision ID: a48b51125920
Revises: 46528ffdfb03
Create Date: 2025-10-16 18:06:59.563045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a48b51125920'
down_revision: Union[str, None] = '46528ffdfb03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE VIEW v_dte_detail AS
    SELECT h.id AS header_id, h.tipo_dte, h.folio, h.fecha_emision,
           h.rut_emisor, h.razon_social_emisor, h.rut_receptor, h.razon_social_receptor,
           h.mnt_neto, h.iva, h.mnt_total,
           d.id AS detail_id, d.nro_linea, d.tipo_codigo, d.codigo,
           d.nombre_item, d.descripcion, d.cantidad, d.precio_unitario, d.monto_item
    FROM dte_headers h
    JOIN dte_details d ON d.header_id = h.id;
    """)
    op.execute("""
    CREATE OR REPLACE VIEW v_dte_kpi_daily AS
    SELECT fecha_emision::date AS dia,
           COUNT(*) AS dtes,
           SUM(mnt_total) AS monto_total
    FROM dte_headers
    GROUP BY 1
    ORDER BY 1;
    """)

def downgrade():
    op.execute("DROP VIEW IF EXISTS v_dte_kpi_daily;")
    op.execute("DROP VIEW IF EXISTS v_dte_detail;")