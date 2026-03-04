from sqlalchemy.orm import Session
from app.models.dte import DteDetail
from app.services.ai_taxonomy import classify, AI_VERSION

def enrich_all_details(db: Session, limit: int = 5000, force: bool = False) -> int:
    q = db.query(DteDetail)

    if not force:
        q = q.filter(
            (DteDetail.ai_version.is_(None)) |
            (DteDetail.ai_version != AI_VERSION)
        )

    q = q.order_by(DteDetail.id.desc()).limit(limit)

    rows = q.all()
    n = 0
    for r in rows:
        res = classify(r.codigo, r.nombre_item or r.descripcion or "", r.descripcion)
        r.ai_category    = res["ai_category"]
        r.ai_subcategory = res["ai_subcategory"]
        r.ai_brand       = res["ai_brand"]
        r.ai_attrs       = res["ai_attrs"]
        r.ai_confidence  = res["ai_confidence"]
        r.ai_version     = res["ai_version"]
        n += 1
    if n:
        db.commit()
    return n
