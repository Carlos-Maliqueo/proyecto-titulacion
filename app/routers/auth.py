from fastapi import APIRouter, Depends, Form, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import SessionLocal
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User
from app.models.role import Role
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("/login")
def login(response: Response, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email_norm = (email or "").strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if not user or not verify_password(password, user.hashed_password):
        return Response("Credenciales inválidas", status_code=401)

    token = create_access_token({"sub": user.email, "roles": [r.name for r in user.roles]})

    app_base = settings.APP_BASE_URL or ""
    secure_cookie = app_base.startswith("https")

    resp = Response(status_code=303, headers={"Location": "/home"})
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
    )
    return resp


@router.post("/logout")
def logout():
    resp = Response(status_code=303, headers={"Location": "/auth/login"})
    resp.delete_cookie("access_token")
    return resp

# Utilidad: crear usuarios (para bootstrap)
@router.post("/seed")
def seed_users(db: Session = Depends(get_db)):
    # 1) Asegurar roles
    for name in ("READER", "CONTRIBUTOR", "ADMIN"):
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name))
    db.commit()

    def upsert_user(email: str, password: str, roles: list[str]):
        email_norm = (email or "").strip().lower()
        u = db.query(User).filter(func.lower(User.email) == email_norm).first()
        if not u:
            u = User(email=email_norm, hashed_password=get_password_hash(password))
            if hasattr(u, "is_active"):
                setattr(u, "is_active", True)
            db.add(u); db.flush()
        else:
            u.hashed_password = get_password_hash(password)
            if hasattr(u, "is_active"):
                setattr(u, "is_active", True)

        u.roles = [db.query(Role).filter(Role.name == r).one() for r in roles]
        db.commit()

    # 2) Usuarios demo (se crean o actualizan)
    upsert_user("reader@example.com",  "reader123",  ["READER"])
    upsert_user("contrib@example.com", "contrib123", ["CONTRIBUTOR"])
    upsert_user("admin@example.com",   "admin123",   ["ADMIN"])

    return {"ok": True}
