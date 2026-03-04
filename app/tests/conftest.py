from __future__ import annotations

import os, sys
import pytest
from typing import Generator
from types import SimpleNamespace

from starlette.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import event

# --- ensure project root on sys.path ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# --- end ---

from app.main import app
from app.deps import get_db
try:
    from app.deps import get_current_user
    HAS_GET_CURRENT_USER = True
except Exception:
    HAS_GET_CURRENT_USER = False

from app.db.session import SessionLocal
try:
    # si tu módulo expone el engine, mejor usarlo
    from app.db.session import engine as _ENGINE
except Exception:
    _ENGINE = None


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """
    Sesión por test con:
      - Transacción de conexión (rollback al final)
      - SAVEPOINT (begin_nested) que se reabre tras cada commit del app
    Esto evita 'ResourceClosedError' aunque el endpoint haga commit().
    """
    # 1) engine
    engine = _ENGINE
    if engine is None:
        # fallback: obtener el engine desde una sesión temporal
        tmp = SessionLocal()
        engine = tmp.get_bind()
        tmp.close()

    # 2) conexión + transacción exterior
    connection = engine.connect()
    outer_trans = connection.begin()

    # 3) sesión ligada a esa conexión
    TestingSessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session: Session = TestingSessionLocal()

    # 4) SAVEPOINT inicial y re-apertura automática tras cada commit del app
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        # cuando termina un nested (SAVEPOINT) y el padre no es nested, reabrimos otro
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        # cerrar sesión y revertir TODO lo hecho durante el test
        session.close()
        outer_trans.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def override_db(db: Session):
    """
    Hace que todos los endpoints usen 'db' (la sesión de arriba).
    """
    def _override():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = _override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def fake_user():
    """
    Si existe get_current_user, lo sobreescribimos para no requerir login/JWT.
    """
    if not HAS_GET_CURRENT_USER:
        yield
        return

    user_stub = SimpleNamespace(
        id=1,
        email="test@local",
        roles=[SimpleNamespace(name="CONTRIBUTOR")]
    )

    def _override_user():
        return user_stub

    app.dependency_overrides[get_current_user] = _override_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """
    Cliente de pruebas con ciclo de vida limpio.
    """
    with TestClient(app) as c:
        yield c
