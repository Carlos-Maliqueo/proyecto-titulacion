from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.file import File as FileModel
from app.models.dte import DteHeader, DteDetail
from app.models.dq import DqViolation, DqRule

def consistency_report(db: Session) -> dict:
    total_files = db.query(func.count(FileModel.id)).scalar()
    files_with_headers = db.query(func.count(func.distinct(DteHeader.file_id))).scalar()
    headers_total = db.query(func.count(DteHeader.id)).scalar()
    details_total = db.query(func.count(DteDetail.id)).scalar()

    headers_without_details = (
        db.query(func.count(DteHeader.id))
          .outerjoin(DteDetail, DteDetail.header_id == DteHeader.id)
          .filter(DteDetail.id == None)
          .scalar()
    )

    orphan_details = (
        db.query(func.count(DteDetail.id))
          .outerjoin(DteHeader, DteHeader.id == DteDetail.header_id)
          .filter(DteHeader.id == None)
          .scalar()
    )

    # Duplicados por (tipo_dte, folio, rut_emisor)
    dups_q = (
        db.query(DteHeader.tipo_dte, DteHeader.folio, DteHeader.rut_emisor, func.count().label("n"))
          .group_by(DteHeader.tipo_dte, DteHeader.folio, DteHeader.rut_emisor)
          .having(func.count() > 1)
    )
    duplicate_groups = [{"tipo_dte": t, "folio": f, "rut_emisor": r, "n": int(n)} for t,f,r,n in dups_q.limit(50).all()]
    duplicate_groups_count = len(duplicate_groups)

    # Mismatch: suma(detalle.monto_item) vs mnt_total del header (tolerancia 1)
    sumdet = func.coalesce(func.sum(DteDetail.monto_item), 0)
    mism_q = (
        db.query(DteHeader.id, DteHeader.mnt_total, sumdet.label("sumdet"))
          .outerjoin(DteDetail, DteDetail.header_id == DteHeader.id)
          .group_by(DteHeader.id, DteHeader.mnt_total)
          .having(func.abs(func.coalesce(DteHeader.mnt_total,0) - func.coalesce(func.sum(DteDetail.monto_item),0)) > 1)
    )
    totals_mismatch = [{"header_id": hid, "mnt_total": int(total or 0), "sumdet": int(s or 0)} for hid, total, s in mism_q.limit(50).all()]
    totals_mismatch_count = len(totals_mismatch)

    dq_total = db.query(func.count(DqViolation.id)).scalar()
    dq_by_level = dict(db.query(DqRule.level, func.count(DqViolation.id))
                         .join(DqRule, DqRule.id == DqViolation.rule_id)
                         .group_by(DqRule.level).all())

    return {
        "files": {"total": int(total_files or 0), "with_headers": int(files_with_headers or 0)},
        "headers": {
            "total": int(headers_total or 0),
            "without_details": int(headers_without_details or 0),
            "duplicate_groups_count": duplicate_groups_count,
            "duplicate_groups": duplicate_groups,
        },
        "details": {
            "total": int(details_total or 0),
            "orphans": int(orphan_details or 0),
        },
        "totals_check": {
            "mismatch_count": totals_mismatch_count,
            "examples": totals_mismatch,
        },
        "dq": {
            "violations_total": int(dq_total or 0),
            "by_level": {k: int(v) for k, v in dq_by_level.items()},
        }
    }
