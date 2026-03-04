from __future__ import annotations
from uuid import uuid4
from datetime import datetime
from typing import Optional, Iterable, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.runlog import RunLog
from app.models.dq import DqViolation
from app.models.dte import DteDetail


class EtlRun:
    """
    Context manager para registrar una ejecución de ETL y exponer contadores
    usados por etl_jobs.py (files_* / headers_inserted / details_inserted / dq_violations).
    """
    def __init__(self, db: Session, *, job: str, source: Optional[str] = None, note: Optional[str] = None):
        self.db = db
        self.job = job
        self.source = source
        self.note = note
        self.run_id = uuid4().hex

        # Contadores que usa tu job
        self.files_total = 0
        self.files_ok = 0
        self.files_failed = 0
        self.headers_inserted = 0
        self.details_inserted = 0
        self.dq_violations = 0

        # Errores acumulados (se guardan en run_logs.errors)
        self.errors: List[Dict[str, Any]] = []

        # Fila base en run_logs
        self.row = RunLog(
            run_id=self.run_id,
            job=self.job,
            source=self.source,
            status="RUNNING",
            started_at=datetime.utcnow(),
            note=self.note,
        )

    def __enter__(self) -> "EtlRun":
        self.db.add(self.row)
        self.db.flush()   # obtenemos id si lo necesitas
        return self

    def incr(self, **kwargs) -> None:
        """
        Suma contadores: ej. run.incr(files_ok=1, headers_inserted=10)
        """
        for k, v in kwargs.items():
            if not isinstance(v, (int, float)):
                continue
            if not hasattr(self, k):
                setattr(self, k, 0)
            setattr(self, k, getattr(self, k) + int(v))

    def add_error(self, *, where: str, message: str, file_id: Optional[int] = None) -> None:
        self.errors.append({"where": where, "message": message, "file_id": file_id})

    def count_dq_for_headers(self, header_ids: Iterable[int]) -> int:
        """
        Cuenta violaciones DQ relacionadas a headers dados, considerando:
          - entity='header' con entity_id ∈ headers
          - entity='detail' cuyo DteDetail.header_id ∈ headers
        """
        ids = list(header_ids or [])
        if not ids:
            return 0
        q = (
            self.db.query(DqViolation.id)
            .outerjoin(
                DteDetail,
                and_(DqViolation.entity == "detail", DqViolation.entity_id == DteDetail.id),
            )
            .filter(
                or_(
                    and_(DqViolation.entity == "header", DqViolation.entity_id.in_(ids)),
                    and_(DqViolation.entity == "detail", DteDetail.header_id.in_(ids)),
                )
            )
        )
        return q.count()

    def __exit__(self, exc_type, exc, tb) -> None:
        # Status final
        if exc_type is not None:
            final_status = "ERROR"
        elif self.files_failed > 0 or self.errors:
            final_status = "PARTIAL"
        else:
            final_status = "OK"

        # Volcar contadores y cerrar
        self.row.status = final_status
        self.row.ended_at = datetime.utcnow()
        self.row.files_total = self.files_total
        self.row.files_ok = self.files_ok
        self.row.files_failed = self.files_failed
        self.row.headers_inserted = self.headers_inserted
        self.row.details_inserted = self.details_inserted
        self.row.dq_violations = self.dq_violations
        self.row.errors = self.errors or None

        try:
            self.db.add(self.row)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # no suprimir excepciones
        return False
