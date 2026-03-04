from __future__ import annotations

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from pathlib import Path
import sys

# añade la raíz del proyecto al PYTHONPATH (../ arriba desde migrations/)
sys.path.append(str(Path(__file__).resolve().parents[1]))

# importa settings y Base
from app.core.config import settings
from app.db.base import Base

# IMPORTA los módulos para que las tablas queden en Base.metadata
from app.models.dq import DqRule, DqViolation
from app.models.audit import AuditLog
from app.models.dte import DteDetail, DteHeader
from app.models.file import File
from app.models.role import Role
from app.models.user import User
from app.models.dq_health import DqHealth
from app.models.runlog import RunLog

# Alembic Config object
config = context.config

# inyecta la URL de la BD desde settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# logging de Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# metadata objetivo para autogenerate
target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "pyformat"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
