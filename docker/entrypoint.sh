#!/bin/sh
set -e

echo "Esperando base de datos..."
python - <<'PYCODE'
import os, time, sys
import psycopg

raw = os.environ.get("DATABASE_URL")
if not raw:
    print("DATABASE_URL no seteada", file=sys.stderr)
    sys.exit(1)

# Normalizar SQLAlchemy URL -> psycopg URL
raw = raw.replace("postgresql+psycopg://", "postgresql://")

for i in range(60):
    try:
        with psycopg.connect(raw, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        print("DB OK")
        break
    except Exception as e:
        time.sleep(1)
else:
    print("DB no disponible", file=sys.stderr)
    sys.exit(1)
PYCODE

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
