from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

# Configura el engine para SQLite o PostgreSQL (psycopg3) según el URL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        future=True,   # opcional en SQLAlchemy 2.x, no molesta
    )
else:
    # PostgreSQL con psycopg3
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # evita conexiones "muertas"
        pool_size=5,          # ajusta a gusto
        max_overflow=10,      # ajusta a gusto
        future=True,
    )

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # evita que los objetos "expiren" tras commit
)
