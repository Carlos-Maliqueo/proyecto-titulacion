from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import ALGORITHM
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.deps import get_db, require_role
from app.models.runlog import RunLog
from app.services.consistency import consistency_report
from app.services.etl_jobs import etl_daily_job
from datetime import datetime, date

router = APIRouter(prefix="/ops", tags=["ops"])
templates = Jinja2Templates(directory="app/templates")

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

@router.get("/healthz", response_class=JSONResponse, tags=["ops"])
def healthz(db: Session = Depends(get_db), _=Depends(require_role("READER","CONTRIBUTOR"))):
    # 1) ping a DB
    try:
        ok = db.execute(text("SELECT 1")).scalar() == 1
    except Exception as e:
        return JSONResponse(status_code=503, content={"ok": False, "db": False, "error": str(e)})

    # 2) último run
    last = (db.query(RunLog)
              .order_by(RunLog.started_at.desc())
              .limit(1)
              .first())

    # 3) un agregado opcional, backlog simple: archivos sin header
    from app.models.file import File as FileModel
    from app.models.dte import DteHeader
    total_files = db.query(func.count(FileModel.id)).scalar() or 0
    files_with_header = (db.query(func.count(DteHeader.file_id.distinct())).scalar() or 0)
    backlog = total_files - files_with_header

    return {
        "ok": ok,
        "db": True,
        "last_run": {
            "run_id": getattr(last, "run_id", None),
            "job": getattr(last, "job", None),
            "status": getattr(last, "status", None),
            "started_at": getattr(last, "started_at", None),
            "ended_at": getattr(last, "ended_at", None),
        } if last else None,
        "backlog_unparsed_files": backlog,
    }

@router.get("/runs", response_class=HTMLResponse)
def runs_list(
    request: Request, 
    db: Session = Depends(get_db), 
    _=Depends(require_role("ADMIN")),
    job: str | None = Query(default=None),
    status: str | None = Query(default=None),            # RUNNING|OK|ERROR|PARTIAL
    source: str | None = Query(default=None),
    started_from: str | None = Query(default=None),      # YYYY-MM-DD
    started_to: str | None = Query(default=None),        # YYYY-MM-DD
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    started_on_sql = func.date(func.timezone('America/Santiago', RunLog.started_at))

    q = (db.query(
            RunLog.run_id,
            RunLog.job,
            RunLog.source,
            RunLog.started_at,
            RunLog.ended_at,
            RunLog.status,
            RunLog.files_total,
            RunLog.files_ok,
            RunLog.files_failed,
            RunLog.headers_inserted,
            RunLog.details_inserted,
            RunLog.dq_violations,
            started_on_sql.label("started_on"),
        )
        .order_by(RunLog.started_at.desc())
    )

    if job:
        q = q.filter(RunLog.job == job)
    if status:
        q = q.filter(RunLog.status == status)
    if source:
        q = q.filter(RunLog.source.ilike(f"%{source}%"))

    df = _parse_date(started_from)
    dt = _parse_date(started_to)
    if df and dt and df > dt:
        df, dt = dt, df

    if df:
        q = q.filter(started_on_sql >= df)
    if dt:
        q = q.filter(started_on_sql <= dt)

    total = q.count()
    rows = (q.order_by(RunLog.started_at.desc())
              .limit(page_size)
              .offset((page-1)*page_size)
              .all())

    # Para combos
    jobs = [j for (j,) in db.query(RunLog.job).distinct().order_by(RunLog.job).all()]
    statuses = ["RUNNING","OK","ERROR","PARTIAL"]

    # roles para el template
    roles = []
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            roles = payload.get("roles", []) or []
        except JWTError:
            roles = []

    return templates.TemplateResponse(request, "run_logs.html", {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "jobs": jobs,
        "statuses": statuses,
        "filters": {
            "job": job,
            "status": status,
            "source": source,
            "started_from": (df.isoformat() if df else (started_from or "")),
            "started_to": (dt.isoformat() if dt else (started_to or "")),
        },
        "roles": roles,
    })

@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_show(run_id: str, request: Request, db: Session = Depends(get_db), _=Depends(require_role("ADMIN"))):
    row = db.query(RunLog).filter(RunLog.run_id == run_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Run no encontrado")
    # normaliza errores para template
    errors = row.errors or []
    return templates.TemplateResponse(request, "run_show.html", {"r": row, "errors": errors})

@router.get("/consistency", response_class=HTMLResponse)
def consistency(request: Request, db: Session = Depends(get_db), _=Depends(require_role("READER","CONTRIBUTOR"))):
    rep = consistency_report(db)
    return templates.TemplateResponse(request, "consistency.html", {"r": rep})

@router.post("/runs/etl_daily_now")
def etl_daily_now(_=Depends(require_role("ADMIN"))):
    etl_daily_job("manual-trigger")
    return RedirectResponse(url="/ops/runs?msg=triggered", status_code=303)