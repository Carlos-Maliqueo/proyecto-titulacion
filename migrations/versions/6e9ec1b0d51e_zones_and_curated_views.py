"""zones and curated views

Revision ID: 6e9ec1b0d51e
Revises: b7dd69835047
Create Date: 2025-10-19 00:50:23.995297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e9ec1b0d51e'
down_revision: Union[str, None] = 'b7dd69835047'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1) Schemas
    op.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    op.execute("CREATE SCHEMA IF NOT EXISTS stage;")
    op.execute("CREATE SCHEMA IF NOT EXISTS curated;")

    # 2) Stage: proyección directa de tablas actuales
    op.execute("""
    CREATE OR REPLACE VIEW stage.dte_headers AS
    SELECT * FROM public.dte_headers;
    """)
    op.execute("""
    CREATE OR REPLACE VIEW stage.dte_details AS
    SELECT * FROM public.dte_details;
    """)

    # 3) Curated: hecho a nivel línea con flags de DQ
    op.execute("""
    CREATE OR REPLACE VIEW curated.fact_dte_lines AS
    SELECT
      h.id AS header_id,
      d.id AS detail_id,
      h.fecha_emision,
      h.tipo_dte,
      h.folio,
      h.rut_emisor, h.razon_social_emisor,
      h.rut_receptor, h.razon_social_receptor,
      d.nro_linea, d.tipo_codigo, d.codigo, d.nombre_item, d.descripcion,
      d.cantidad, d.precio_unitario, d.monto_item,
      h.mnt_neto, h.iva, h.mnt_total,
      EXISTS (
        SELECT 1
        FROM public.dq_violations v
        JOIN public.dq_rules r ON r.id = v.rule_id
        WHERE v.entity='detail' AND v.entity_id = d.id AND r.level='ERROR'
      ) AS dq_has_error,
      EXISTS (
        SELECT 1
        FROM public.dq_violations v
        JOIN public.dq_rules r ON r.id = v.rule_id
        WHERE v.entity='detail' AND v.entity_id = d.id AND r.level='WARN'
      ) AS dq_has_warn
    FROM public.dte_details d
    JOIN public.dte_headers h ON h.id = d.header_id;
    """)

    # 4) Curated: dimensiones
    op.execute("""
    CREATE OR REPLACE VIEW curated.dim_emisor AS
    SELECT rut_emisor, MAX(razon_social_emisor) AS razon_social_emisor
    FROM public.dte_headers
    GROUP BY rut_emisor;
    """)
    op.execute("""
    CREATE OR REPLACE VIEW curated.dim_receptor AS
    SELECT rut_receptor, MAX(razon_social_receptor) AS razon_social_receptor
    FROM public.dte_headers
    GROUP BY rut_receptor;
    """)

    # 5) Curated: agregados
    op.execute("""
    CREATE OR REPLACE VIEW curated.fct_dte_daily_totals AS
    SELECT
      fecha_emision,
      tipo_dte,
      rut_emisor,
      COUNT(*) AS n_docs,
      SUM(mnt_total) AS monto_total
    FROM public.dte_headers
    GROUP BY fecha_emision, tipo_dte, rut_emisor;
    """)

    # 6) Curated: DQ enriquecido
    op.execute("""
    CREATE OR REPLACE VIEW curated.dq_violations_enriched AS
    SELECT
      v.*,
      r.code  AS rule_code,
      r.level AS rule_level,
      CASE WHEN v.entity='detail' THEN d.header_id ELSE v.entity_id END AS header_id
    FROM public.dq_violations v
    JOIN public.dq_rules r ON r.id=v.rule_id
    LEFT JOIN public.dte_details d
      ON v.entity='detail' AND v.entity_id=d.id;
    """)

def downgrade():
    op.execute("DROP VIEW IF EXISTS curated.dq_violations_enriched;")
    op.execute("DROP VIEW IF EXISTS curated.fct_dte_daily_totals;")
    op.execute("DROP VIEW IF EXISTS curated.dim_receptor;")
    op.execute("DROP VIEW IF EXISTS curated.dim_emisor;")
    op.execute("DROP VIEW IF EXISTS curated.fact_dte_lines;")
    op.execute("DROP VIEW IF EXISTS stage.dte_details;")
    op.execute("DROP VIEW IF EXISTS stage.dte_headers;")
    # (opcional) no borramos los schemas para no romper otras cosas
    # op.execute("DROP SCHEMA IF EXISTS curated;")
    # op.execute("DROP SCHEMA IF EXISTS stage;")
    # op.execute("DROP SCHEMA IF EXISTS raw;")