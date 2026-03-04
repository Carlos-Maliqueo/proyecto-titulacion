from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.deps import get_db, require_role
from app.models.audit import AuditLog
from datetime import datetime, date
from sqlalchemy import func

router = APIRouter(prefix="/audit", tags=["audit"])
templates = Jinja2Templates(directory="app/templates")

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

@router.get("", include_in_schema=False)
@router.get("/", response_class=HTMLResponse)
def audit_list(
    request: Request,
    db: Session = Depends(get_db),
    _user = Depends(require_role("ADMIN")),
    user: str | None = None,
    path: str | None = None,
    method: str | None = None,        
    status: str | None = Query(default=None), # string para tolerar vacio
    date_from: str | None = None,     
    date_to: str | None = None,       
    page: int = 1,
    page_size: int = 50,
):
    created_on_sql = func.date(func.timezone('America/Santiago', AuditLog.ts))

    q = (db.query(
            AuditLog.id,
            AuditLog.ts,
            created_on_sql.label("ts_on"),   
            AuditLog.user,
            AuditLog.path,
            AuditLog.method,
            AuditLog.status,
            AuditLog.action,
            AuditLog.resource,
            AuditLog.resource_id,
            AuditLog.extra,
        )
        .order_by(AuditLog.ts.desc())
    )

    # filtros
    if user:
        q = q.filter(AuditLog.user == user)
    if path:
        q = q.filter(AuditLog.path.ilike(f"%{path}%"))
    if method:
        q = q.filter(AuditLog.method == method)
    if status not in (None, ""):
        try:
            q = q.filter(AuditLog.status == int(status))
        except ValueError:
            # si no es número, ignoramos el filtro (o podrías devolver 400)
            pass
    
    # Parsear fechas del querystring
    df = _parse_date(date_from)
    dt = _parse_date(date_to)

    # Si vienen invertidas, las ordenamos para no fallar
    if df and dt and df > dt:
        df, dt = dt, df

    # Filtro por día en zona 'America/Santiago'
    if df:
        q = q.filter(created_on_sql >= df)
    if dt:
        q = q.filter(created_on_sql <= dt)

    # paginacion
    total = q.count()
    rows = q.limit(page_size).offset((page-1)*page_size).all()

    return templates.TemplateResponse(request, "audit.html", {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "filters": {
            "user": user,
            "path": path,
            "method": method,
            "status": status,
            # devolver normalizado para que el date input muestre bien
            "date_from": (df.isoformat() if df else (date_from or "")),
            "date_to": (dt.isoformat() if dt else (date_to or "")),
        }
    })
