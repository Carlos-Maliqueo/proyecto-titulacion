from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import SessionLocal
from app.models.user import User

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")

    if token.startswith("Bearer "):
        token = token[7:]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    
    user_roles = [r.name.upper() for r in getattr(user, "roles", [])]
    request.state.roles = user_roles
    request.state.user_email = user.email
    
    return user

def require_role(*allowed: str):
    allowed_set = {r.upper() for r in allowed}

    def checker(user: User = Depends(get_current_user)):
        user_roles = {r.name.upper() for r in getattr(user, "roles", [])}

        if "ADMIN" in user_roles:
            return user

        if not allowed_set:
            return user

        if user_roles & allowed_set:
            return user

        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    
    return checker
