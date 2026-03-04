from __future__ import annotations
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from app.models.runlog import RunLog
from app.models.dq_health import DqHealth
from app.core.config import settings

def _today_tz() -> date:
    tz = ZoneInfo(settings.SCHEDULER_TIMEZONE)
    return datetime.now(tz).date()

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def _compute_score(viol_total: int, headers: int) -> float:
    """
    v1 simple: score = 100 - 100*(violations_total / max(headers,1))
    Si 10% de headers tienen violaciones => score 90.
    """
    if headers <= 0:
        return 100.0  # sin datos => 100 (ajustable)
    rate = viol_total / float(headers)
    return round(_clamp(100.0 - 100.0 * rate, 0.0, 100.0), 2)

def compute_daily_health(db: Session, day: date | None = None) -> DqHealth:
    """
    Agrega métricas desde RunLog del día (job=etl_daily).
    """
    d = day or _today_tz()

    q = (db.query(
            func.coalesce(func.sum(RunLog.headers_inserted), 0),
            func.coalesce(func.sum(RunLog.details_inserted), 0),
            func.coalesce(func.sum(RunLog.dq_violations), 0),
        )
        .filter(RunLog.job == "etl_daily")
        .filter(cast(RunLog.started_at, Date) == d)
    )
    headers, details, viol_total = q.one()

    score = _compute_score(viol_total, headers)

    return DqHealth(
        day=d,
        headers=int(headers or 0),
        details=int(details or 0),
        violations_total=int(viol_total or 0),
        score=score,
    )

def compute_and_store_daily_health(db: Session, day: date | None = None) -> DqHealth:
    row = compute_daily_health(db, day)
    # UPSERT manual (por simplicidad)
    existing = db.query(DqHealth).filter(DqHealth.day == row.day).first()
    if existing:
        existing.headers = row.headers
        existing.details = row.details
        existing.violations_total = row.violations_total
        existing.score = row.score
        db.commit()
        db.refresh(existing)
        return existing
    else:
        db.add(row); db.commit(); db.refresh(row)
        return row
