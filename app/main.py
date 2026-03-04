from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.staticfiles import StaticFiles
from app.routers import auth, files, pages, etl, dte, dq, audit, ops, ai
from app.db.session import SessionLocal
from app.services.scheduler import start_scheduler, shutdown_scheduler, schedule_daily_etl
from app.models.audit import AuditLog
from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import ALGORITHM
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Gosocket ETL")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
# Rutas
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(etl.router)
app.include_router(dte.router)
app.include_router(pages.router)
app.include_router(dq.router)
app.include_router(audit.router)
app.include_router(ops.router)
app.include_router(ai.router)

@app.on_event("startup")
def _on_startup():
    if settings.SCHEDULER_ENABLED:
        start_scheduler()
        schedule_daily_etl()
        log.info("APScheduler iniciado: cron=%s tz=%s",
                 settings.SCHEDULER_CRON, settings.SCHEDULER_TIMEZONE)

@app.on_event("shutdown")
def _on_shutdown():
    if settings.SCHEDULER_ENABLED:
        shutdown_scheduler()


@app.get("/health")
def health():
    return {"ok": True}

@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    # redirige a login en 401/403
    if exc.status_code in (401, 403):
        resp = RedirectResponse("/auth/login", status_code=303)
        if request.cookies.get("access_token"):
            resp.delete_cookie("access_token")
        return resp
    # para el resto se usa el handler por defecto de FastAPI
    return await default_http_exception_handler(request, exc)

@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    # opcional: no auditar healthcheck ni static
    if request.url.path in ("/health", "/favicon.ico"):
        return await call_next(request)

    # intenta extraer el email del JWT, si existe
    user_email = None
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            user_email = payload.get("sub")
        except JWTError:
            user_email = None

    # Para que los templates conozcan roles
    request.state.roles = []
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            request.state.roles = payload.get("roles", []) or []
        except JWTError:
            request.state.roles = []

    response = await call_next(request)

    # escribe registro en DB (sin romper el request si falla)
    try:
        db = SessionLocal()
        db.add(AuditLog(
            user=user_email or "-",
            path=str(request.url.path),
            method=request.method,
            status=response.status_code,
        ))
        db.commit()
    except Exception:
        pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    return response
