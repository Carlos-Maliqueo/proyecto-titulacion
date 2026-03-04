from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import ALGORITHM
from app.deps import get_current_user, get_db
from app.models.file import File as FileModel

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/auth/login", response_class=HTMLResponse)
def login_page(request: Request):
    last_email = request.cookies.get("last_email")
    return templates.TemplateResponse(request, "login.html", {"last_email": last_email})

@router.get("/", include_in_schema=False)
def root(request: Request):
    raw = request.cookies.get("access_token")
    if raw:
        token = raw.split(" ", 1)[1] if raw.startswith("Bearer ") else raw
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("sub"):
                return RedirectResponse(url="/home", status_code=303)
        except JWTError:
            pass  

    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp

@router.get("/home", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db), user = Depends(get_current_user)):
    # Serializamos a dicts simples para evitar problemas con objetos ORM en plantillas
    recs = db.query(FileModel).order_by(FileModel.created_at.desc()).all()
    files_ctx = [
        {
            "id": r.id,
            "filename": r.filename,
            "uploader_email": getattr(getattr(r, "uploader", None), "email", None),
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for r in recs
    ]
    roles = [role.name for role in getattr(user, "roles", [])]
    can_upload = "CONTRIBUTOR" in roles
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "user_email": getattr(user, "email", ""),
            "roles": roles,
            "can_upload": can_upload,
            "files": files_ctx,
        },
    )

# Evita 404 de favicon en desarrollo
@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
