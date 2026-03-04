from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text, nulls_last, or_
from app.deps import get_db, require_role
from app.services.ai_enricher import enrich_all_details
from app.models.dte import DteDetail

router = APIRouter(prefix="/ai", tags=["ai"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/items", response_class=HTMLResponse)
def ai_items(
    request: Request, 
    cat: str, 
    sub: str, 
    db: Session = Depends(get_db), 
    _=Depends(require_role("READER","CONTRIBUTOR"))):

    q = db.query(DteDetail).filter(DteDetail.ai_category == cat)

    if sub in (None, "", "-", "null", "__none__"):
        q = q.filter(DteDetail.ai_subcategory.is_(None))
    else:
        q = q.filter(DteDetail.ai_subcategory == sub)

    rows = (q.order_by(nulls_last(DteDetail.monto_item.desc()))
             .limit(200)
             .all())

    return templates.TemplateResponse("ai_items.html", {
        "request": request,
        "rows": rows,
        "cat": cat,
        "sub": sub
    })

@router.post("/enrich")
def ai_enrich(force: bool = Query(default=False), db: Session = Depends(get_db), _=Depends(require_role("CONTRIBUTOR"))):
    n = enrich_all_details(db, limit=10000, force=force)
    return RedirectResponse(url=f"/ai/overview?enriched={n}", status_code=303)

@router.get("/overview", response_class=HTMLResponse)
def ai_overview(request: Request, db: Session = Depends(get_db), _=Depends(require_role("READER","CONTRIBUTOR"))):
    # mix por categoría/sub
    mix = (db.query(
                DteDetail.ai_category,
                DteDetail.ai_subcategory,
                func.count().label("n"),
                func.sum(DteDetail.monto_item).label("rev")
            )
            .filter(DteDetail.ai_category.isnot(None))
            .group_by(DteDetail.ai_category, DteDetail.ai_subcategory)
            .order_by(desc("rev"))
            .limit(30).all())

    # top marcas
    brands = (db.query(
                DteDetail.ai_brand,
                func.count().label("n"),
                func.sum(DteDetail.monto_item).label("rev")
            )
            .filter(DteDetail.ai_brand.isnot(None))
            .group_by(DteDetail.ai_brand)
            .order_by(desc("rev"))
            .limit(20).all())

    # tasa sin clasificar
    total = db.query(func.count()).select_from(DteDetail).scalar()
    uncls = db.query(func.count()).select_from(DteDetail).filter(DteDetail.ai_category.is_(None)).scalar()
    rate = round((uncls or 0) * 100.0 / (total or 1), 2)

    # co-ocurrencias (armas bundle/cross-sell por subcategoría)
    pairs = db.execute(text("""
        with dd as (
        select header_id, ai_subcategory sub, id
        from dte_details
        where ai_subcategory is not null
        )
        select least(a.sub,b.sub) as s1, greatest(a.sub,b.sub) as s2, count(*) as n
        from dd a join dd b on a.header_id=b.header_id and a.id<b.id
        group by 1,2
        having count(*) >= 3
        order by n desc
        limit 20;
    """)).fetchall()

    return templates.TemplateResponse(request, "ai_overview.html", {
        "mix": mix,
        "brands": brands,
        "uncls_rate": rate,
        "pairs": pairs,
        "enriched": request.query_params.get("enriched"),
    })
