from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, case, desc, func
from app.deps import get_db, require_role
from app.services.dq_health import compute_and_store_daily_health
from app.models.dq import DqViolation, DqRule
from app.models.dte import DteDetail
from app.models.dq_health import DqHealth
from app.models.runlog import RunLog
from datetime import datetime, date, timedelta

router = APIRouter(prefix="/dq", tags=["dq"])
templates = Jinja2Templates(directory="app/templates")

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

@router.get("/violations", response_class=HTMLResponse)
def list_violations(
    request: Request,
    db: Session = Depends(get_db),
    _user = Depends(require_role("READER","CONTRIBUTOR")),
    code: str | None = None,
    level: str | None = None,         # 'ERROR' | 'WARN'
    entity: str | None = None,        # 'header' | 'detail'
    header_id: str | None = Query(default=None),
    date_from: str | None = None,     # 'YYYY-MM-DD'
    date_to: str | None = None,       # 'YYYY-MM-DD'
    page: int = 1,
    page_size: int = 50,
):
    # header_id (para link): si es header -> entity_id; si es detail -> join a DteDetail.header_id
    header_id_expr = case(
        (DqViolation.entity == "header", DqViolation.entity_id),
        else_=DteDetail.header_id
    ).label("header_id")

    created_on_sql = func.date(func.timezone('America/Santiago', DqViolation.created_at))

    q = (db.query(
            DqViolation.id,
            DqViolation.created_at,
            created_on_sql.label("created_on"),
            DqViolation.entity,
            DqViolation.entity_id,
            DqViolation.message,
            DqRule.code.label("rule_code"),
            DqRule.level.label("rule_level"),
            header_id_expr
        )
        .join(DqRule, DqRule.id == DqViolation.rule_id)
        .outerjoin(DteDetail, and_(DqViolation.entity=="detail", DqViolation.entity_id==DteDetail.id))
        .order_by(DqViolation.created_at.desc())
    )

    if code:
        q = q.filter(DqRule.code == code)

    if level:
        q = q.filter(DqRule.level == level)
        
    if entity:
        q = q.filter(DqViolation.entity == entity)
    
    hid = None
    if header_id is not None and header_id.strip() != "":
        try:
            hid = int(header_id.strip())
        except ValueError:
            hid = None  # si viene invalido se ignora el filtro

    if hid is not None:
        q = q.filter(
            or_(
                and_(DqViolation.entity == "header", DqViolation.entity_id == hid),
                and_(DqViolation.entity == "detail", DteDetail.header_id == hid),
            )
        )

    # Parsear fechas del querystring
    df = _parse_date(date_from)
    dt = _parse_date(date_to)

    # Si vienen invertidas, las intercambiamos para no romper
    if df and dt and df > dt:
        df, dt = dt, df

    # Filtro por día en zona 'America/Santiago'
    if df:
        q = q.filter(created_on_sql >= df)
    if dt:
        q = q.filter(created_on_sql <= dt)


    # paginación simple
    total = q.count()
    rows = q.limit(page_size).offset((page-1)*page_size).all()

    # para el combo de reglas/levels en el filtro
    codes = [c for (c,) in db.query(DqRule.code).order_by(DqRule.code).all()]
    levels = ["ERROR","WARN"]

    return templates.TemplateResponse(request, "dq_violations.html", {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "codes": codes,
        "levels": levels,
        "filters": {
            "code":code,
            "level":level,
            "entity":entity,
            "header_id":header_id,
            "date_from": (df.isoformat() if df else (date_from or "")),
            "date_to": (dt.isoformat() if dt else (date_to or "")),
        },
    })

@router.get("/summary", response_class=HTMLResponse)
def dq_summary(request: Request, db: Session = Depends(get_db), _=Depends(require_role("READER","CONTRIBUTOR"))):
    from sqlalchemy import func
    # por nivel
    lvl = (db.query(DqRule.level, func.count(DqViolation.id))
             .join(DqViolation, DqViolation.rule_id==DqRule.id)
             .group_by(DqRule.level).all())
    # por regla
    rules = (db.query(DqRule.code, func.count(DqViolation.id))
               .join(DqViolation, DqViolation.rule_id==DqRule.id)
               .group_by(DqRule.code).all())
    # por día
    perday = (db.query(func.date(DqViolation.created_at), func.count())
                .group_by(func.date(DqViolation.created_at))
                .order_by(func.date(DqViolation.created_at)).all())
    d = {
      "by_level": [{"level": l, "n": int(n)} for l,n in lvl],
      "by_rule": [{"code": c, "n": int(n)} for c,n in rules],
      "by_day": [{"day": str(d), "n": int(n)} for d,n in perday],
    }
    # si no se quiere template, se devuelve JSON:
    return templates.TemplateResponse(request, "dq_summary.html", {"data": d})

@router.get("/health", response_class=HTMLResponse)
def dq_health_view(request: Request, db: Session = Depends(get_db), _=Depends(require_role("ADMIN"))):
    from statistics import mean

    rows = (db.query(DqHealth)
              .order_by(desc(DqHealth.day))
              .limit(30)
              .all())
    last = rows[0] if rows else None

    # Construye series (antiguo -> reciente) para graficar homogéneo en X
    series_scores = [float(r.score) for r in reversed(rows)]
    series_viol   = [int(r.violations_total) for r in reversed(rows)]

    def _spark_points(values, w=240, h=40, pad=2):
        if not values:
            return "", (0, 0)
        n = len(values)
        xmin, xmax = pad, w - pad
        if n == 1:
            xs = [(xmin + xmax) / 2]
        else:
            xs = [xmin + i * (xmax - xmin) / (n - 1) for i in range(n)]
        vmin = min(values)
        vmax = max(values)
        if vmax == vmin:
            vmax = vmin + 1.0
        def y(v):
            return pad + (h - 2 * pad) * (1 - (v - vmin) / (vmax - vmin))
        pts = [f"{xs[i]:.1f},{y(values[i]):.1f}" for i in range(n)]
        return " ".join(pts), (vmin, vmax)

    pts_score, range_score = _spark_points(series_scores)
    pts_viol,  range_viol  = _spark_points(series_viol)

    def _avg_last(values, k):
        if not values:
            return None
        take = values[-k:] if len(values) >= k else values
        return round(mean(take), 2)

    stats = {
        "avg7": _avg_last(series_scores, 7),
        "avg30": _avg_last(series_scores, 30),
        "delta1": round(series_scores[-1] - series_scores[-2], 2) if len(series_scores) >= 2 else None,
        "best_day": max(rows, key=lambda r: r.score) if rows else None,
        "worst_day": min(rows, key=lambda r: r.score) if rows else None,
    }

    # ---- KPIs operacionales ETL (últimos 30 días) ----
    today = datetime.utcnow().date()
    since = today - timedelta(days=30)

    # segundos de duración = EXTRACT(EPOCH FROM ended_at - started_at)
    duration_sec = func.extract('epoch', RunLog.ended_at - RunLog.started_at)

    q_etl = (db.query(
                func.avg(duration_sec),
                func.max(duration_sec),
                func.count(),
                func.sum(case((RunLog.status=='OK', 1), else_=0))
            )
            .filter(RunLog.job == 'etl_daily')
            .filter(RunLog.started_at >= since)
            .filter(RunLog.ended_at.isnot(None))
    )

    avg_sec, max_sec, runs_total, runs_ok = q_etl.one()
    success_rate = (float(runs_ok) * 100.0 / float(runs_total)) if runs_total else None

    ops_metrics = {
        "avg_sec": round(float(avg_sec or 0), 2),
        "max_sec": round(float(max_sec or 0), 2),
        "runs_total": int(runs_total or 0),
        "runs_ok": int(runs_ok or 0),
        "success_rate": round(success_rate, 2) if success_rate is not None else None,
    }

    return templates.TemplateResponse(request, "dq_health.html", {
        "rows": rows,
        "last": last,
        "spark": {
            "score": {"pts": pts_score, "range": range_score},
            "viol":  {"pts": pts_viol,  "range": range_viol},
        },
        "stats": stats,
        "ops_metrics": ops_metrics,
    })

@router.post("/health/recompute")
def dq_health_recompute(db: Session = Depends(get_db), _=Depends(require_role("ADMIN"))):
    compute_and_store_daily_health(db)
    return RedirectResponse(url="/dq/health?ok=1", status_code=303)