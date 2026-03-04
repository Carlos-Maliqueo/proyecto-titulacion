from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.file import File as FileModel
from app.models.dte import DteDetail
from app.services.dte_parser import parse_and_store_xml
from app.services.etl_run import EtlRun
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import os

from app.services.notify import notify
from app.services.dq_health import compute_and_store_daily_health

UPLOAD_DIR = "app/uploads"

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((Exception,))
)
def _parse_one(rec: FileModel, path: str, db: Session, run_id: str) -> tuple[list[int], int]:
    """
    Parsea un archivo y retorna (header_ids, n_details)
    con reintentos automáticos (Tenacity) para errores transitorios.
    """
    header_ids = parse_and_store_xml(rec, path, db, run_id=run_id)
    n_details = 0
    if header_ids:
        n_details = db.query(DteDetail).filter(DteDetail.header_id.in_(header_ids)).count()
    return header_ids, n_details

def _acquire_lock(db: Session) -> bool:
    # Advisory lock para evitar dos etl_daily en paralelo
    key = getattr(settings, "ETL_ADVISORY_LOCK_KEY", 20250101)  # default si no está en .env
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar())

def _release_lock(db: Session) -> None:
    key = getattr(settings, "ETL_ADVISORY_LOCK_KEY", 20250101)
    db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})

def _notify_dq_threshold(db: Session, run_id: str, details_inserted: int, threshold_per_100: float = 1.0) -> None:
    """
    Alerta si las violaciones DQ de ESTA corrida superan el umbral por 100 líneas procesadas.
    Numerador: dq_violations con run_id actual.
    Denominador: details_inserted de la corrida (evita usar todo el histórico).
    """
    # defensivo: evita división por cero
    denom = max(details_inserted or 0, 1)

    viol = db.execute(
        text("SELECT COUNT(*)::int FROM dq_violations WHERE run_id = :rid"),
        {"rid": run_id}
    ).scalar() or 0

    viol_x_100 = (viol * 100.0) / denom

    if viol_x_100 >= threshold_per_100:
        notify(
            subject=f"DQ alerta: {viol_x_100:.2f} viol/100 líneas",
            text=f"Se superó el umbral ({threshold_per_100}/100) en run {run_id}.",
            severity="WARN",
            payload={"run_id": run_id, "viol_x_100": float(viol_x_100), "viol": viol, "lines": denom}
        )


def etl_daily_job(source: str = "gosocket"):
    db: Session = SessionLocal()
    got_lock = False
    try:
        got_lock = _acquire_lock(db)
        if not got_lock:
            # Ya hay otro job corriendo, salimos sin error
            return

        with EtlRun(db, job="etl_daily", source=source, note="carga incremental diaria") as run:
            # Descubre XMLs en disco que aún no tengan registro en files
            filenames = [f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".xml")]
            to_process: list[FileModel] = []
            for fn in filenames:
                exists = db.query(FileModel.id).filter(FileModel.filename == fn).first()
                if not exists:
                    rec = FileModel(filename=fn, uploader_id=None)
                    db.add(rec); db.flush()
                    to_process.append(rec)
            db.commit()

            run.incr(files_total=len(to_process))

            for rec in to_process:
                path = os.path.join(UPLOAD_DIR, rec.filename)
                if not os.path.exists(path):
                    run.add_error(where="etl_daily.missing_file", message=f"no existe {path}", file_id=rec.id)
                    run.incr(files_failed=1)
                    continue

                try:
                    header_ids, n_details = _parse_one(rec, path, db, run_id=run.run_id)
                    db.commit()  # por si el parser no hizo commit interno
                    run.incr(files_ok=1, headers_inserted=len(header_ids), details_inserted=n_details)
                    if header_ids:
                        run.incr(dq_violations=run.count_dq_for_headers(header_ids))
                except Exception as e: 
                    db.rollback()
                    run.incr(files_failed=1)
                    run.add_error(where="etl_daily.parse", message=str(e), file_id=rec.id)
            # snapshot de salud DQ para hoy y aviso a Slack
            health = compute_and_store_daily_health(db)  # retorna (day, headers, details, viol_total, score)
            _notify_dq_threshold(db, run.run_id, run.details_inserted, threshold_per_100=1.0)
            
            app_base = settings.APP_BASE_URL or "http://localhost:8000"
            run_url = f"{app_base}/ops/runs/{run.run_id}"

            notify(
                subject="ETL daily OK",
                text=f"run_id={run.run_id}",
                severity="INFO",
                payload={
                    "run_id": run.run_id,
                    "files": f"{run.files_ok}/{run.files_total} (fail: {run.files_failed or 0})",
                    "headers": run.headers_inserted or 0,
                    "details": run.details_inserted or 0,
                    "DQ violations": run.dq_violations or 0,
                    "DQ score": getattr(health, 'score', None),
                    "open": run_url,
                },
            )
    except Exception as e:
        # avisar error a Slack
        app_base = settings.APP_BASE_URL or "http://localhost:8000"
        # No tenemos run_id si falló antes del contexto, así que lo manejamos defensivo.
        try:
            rid = run.run_id  # si existe
        except:
            rid = "N/A"
        notify(
            subject="ETL daily ERROR",
            text=str(e),
            severity="ERROR",
            payload={"run_id": rid, "open": f"{app_base}/ops/runs/{rid}"}
        )
        raise
    finally:
        try:
            if got_lock:
                _release_lock(db)
        finally:
            db.close()
