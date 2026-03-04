from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from app.deps import get_db, require_role
from app.models.file import File as FileModel
from app.models.dte import DteHeader, DteDetail
from app.services.dte_parser import parse_and_store_xml
from fastapi.templating import Jinja2Templates
from app.services.xml_schema import validate_with_xsd, pick_xsd_path_for_xml
from app.core.config import settings
from app.services.audit import audit_action
from app.services.etl_run import EtlRun
import os, io, csv
from datetime import datetime, date

router = APIRouter(prefix="/etl", tags=["etl"])
templates = Jinja2Templates(directory="app/templates")
UPLOAD_DIR = "app/uploads"

@router.post("/parse/{file_id}")
def parse_file(file_id: int,
               request: Request,
               db: Session = Depends(get_db),
               _user = Depends(require_role("CONTRIBUTOR"))):
    rec = db.get(FileModel, file_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Archivo no existe")

    path = os.path.join(UPLOAD_DIR, rec.filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado")

    if not rec.filename.lower().endswith(".xml"):
        return RedirectResponse(url="/home?msg=solo-xml-por-ahora", status_code=303)

    # Logging operativo de la corrida manual
    with EtlRun(db, job="manual_parse", source="ui", note=f"file_id={rec.id}") as run:
        # Validación XSD
        xsd_path = pick_xsd_path_for_xml(path)
        if xsd_path and os.path.exists(xsd_path):
            errs = validate_with_xsd(path, xsd_path)
            if errs:
                audit_action(
                    db,
                    getattr(_user, "email", None),
                    "xsd_invalid",
                    resource="file",
                    resource_id=rec.id,
                    extra={"filename": rec.filename, "n_errors": len(errs), "first_errors": errs[:5]},
                    status=422
                )
                run.add_error(where="xsd_validate", message="; ".join(errs[:3]), file_id=rec.id)
                run.set_status("PARTIAL")  # o "ERROR" si prefieres bloquear
                return templates.TemplateResponse(request, "xsd_errors.html", {"filename": rec.filename, "errors": errs}, status_code=422,
                )

        # Parseo
        header_ids = parse_and_store_xml(rec, path, db, run_id=run.run_id)

        # Contadores de run
        run.incr(files_total=1, files_ok=1, headers_inserted=len(header_ids))
        if header_ids:
            details_count = db.query(DteDetail).filter(DteDetail.header_id.in_(header_ids)).count()
            run.incr(details_inserted=details_count)
            run.incr(dq_violations=run.count_dq_for_headers(header_ids))

        # AUDIT: parse realizado
        audit_action(
            db,
            getattr(_user, "email", None),
            "xml_parse",
            resource="file",
            resource_id=rec.id,
            extra={"filename": rec.filename, "n_headers": len(header_ids), "headers": header_ids},
            status=303
        )

        return RedirectResponse(url="/etl/dtes?parsed=1", status_code=303)

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def _apply_dtes_filters(q, *, tipo, folio, df, dt, emisor, receptor):
    if tipo not in (None, ""):
        try:
            tipo_int = int(str(tipo).strip())
            q = q.filter(DteHeader.tipo_dte == tipo_int)
        except ValueError:  
            pass
    if folio not in (None, ""):
        try:
            q = q.filter(DteHeader.folio == int(str(folio).strip()))
        except ValueError:
            pass
    if df:
        q = q.filter(DteHeader.fecha_emision >= df)
    if dt:
        q = q.filter(DteHeader.fecha_emision <= dt)

    if emisor:
        term = f"%{emisor.strip()}%"
        q = q.filter(or_(DteHeader.rut_emisor.ilike(term),
                         DteHeader.razon_social_emisor.ilike(term)))
    if receptor:
        term = f"%{receptor.strip()}%"
        q = q.filter(or_(DteHeader.rut_receptor.ilike(term),
                         DteHeader.razon_social_receptor.ilike(term)))
    return q

@router.get("/dtes", response_class=HTMLResponse)
def list_dtes(
    request: Request, 
    db: Session = Depends(get_db), 
    _user = Depends(require_role("READER", "CONTRIBUTOR", "ADMIN")), # desde aca nuevo
    tipo: str | None = Query(default=None),
    folio: str | None = Query(default=None),
    fecha_from: str | None = Query(default=None),
    fecha_to: str | None = Query(default=None),
    emisor: str | None = Query(default=None),
    receptor: str | None = Query(default=None),
    limit: int = Query(500, ge=1, le=5000),
    ):
    df = _parse_date(fecha_from)
    dt = _parse_date(fecha_to)
    if df and dt and df > dt:
        df, dt = dt, df

    q = db.query(DteHeader)
    q = _apply_dtes_filters(q, tipo=tipo, folio=folio, df=df, dt=dt, emisor=emisor, receptor=receptor)
    rows = (q.order_by(DteHeader.id.desc())
              .limit(limit)
              .all())

    # Para combo de tipos
    tipos = [t for (t,) in db.query(DteHeader.tipo_dte).distinct().order_by(DteHeader.tipo_dte).all()]

    return templates.TemplateResponse(request, "dtes.html", {
        "rows": rows,
        "tipos": tipos,
        "filters": {
            "tipo": tipo or "",
            "folio": folio or "",
            "fecha_from": (df.isoformat() if df else (fecha_from or "")),
            "fecha_to": (dt.isoformat() if dt else (fecha_to or "")),
            "emisor": emisor or "",
            "receptor": receptor or "",
            "limit": limit,
        }
    })
    #rows = (db.query(DteHeader)
    #         .order_by(DteHeader.id.desc())
    #          .limit(200)
    #          .all())
    #return templates.TemplateResponse(request, "dtes.html", {"rows": rows})

@router.get("/dtes/export")
def export_dtes_csv(
    db: Session = Depends(get_db),
    _user = Depends(require_role("READER","CONTRIBUTOR","ADMIN")),
    tipo: str | None = Query(default=None),
    folio: str | None = Query(default=None),
    fecha_from: str | None = Query(default=None),
    fecha_to: str | None = Query(default=None),
    emisor: str | None = Query(default=None),
    receptor: str | None = Query(default=None),
):
    df = _parse_date(fecha_from)
    dt = _parse_date(fecha_to)
    if df and dt and df > dt:
        df, dt = dt, df

    q = db.query(DteHeader)
    q = _apply_dtes_filters(q, tipo=tipo, folio=folio, df=df, dt=dt, emisor=emisor, receptor=receptor)
    rows = q.order_by(DteHeader.id.desc()).all()

    # Generar CSV (Excel lo abre sin problemas)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID","Tipo","Folio","Fecha","Emisor","Receptor","Monto Total"])
    for h in rows:
        w.writerow([
            h.id, h.tipo_dte, h.folio, h.fecha_emision,
            h.rut_emisor, h.rut_receptor, h.mnt_total
        ])
    data = buf.getvalue()
    buf.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {"Content-Disposition": f'attachment; filename="dtes_{ts}.csv"'}
    return Response(content=data, media_type="text/csv; charset=utf-8", headers=headers)

@router.get("/dte/{header_id}", response_class=HTMLResponse)
def show_dte(header_id: int,
             request: Request,
             db: Session = Depends(get_db),
             _user = Depends(require_role("READER","CONTRIBUTOR", "ADMIN"))):
    hdr = (db.query(DteHeader)
             .options(joinedload(DteHeader.detalles))
             .filter(DteHeader.id == header_id)
             .first())
    if not hdr:
        raise HTTPException(status_code=404, detail="DTE no encontrado")
    return templates.TemplateResponse(request, "dte_show.html", {"hdr": hdr})

@router.get("/dte/{header_id}/export_pdf")
def dte_export_pdf(header_id: int, db: Session = Depends(get_db), _=Depends(require_role("READER","CONTRIBUTOR","ADMIN"))):
    hdr = (db.query(DteHeader)
             .options(joinedload(DteHeader.detalles))
             .filter(DteHeader.id == header_id)
             .first())
    if not hdr:
        raise HTTPException(status_code=404, detail="DTE no encontrado")

    # Generar PDF con reportlab
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
    except ImportError:
        # Si falta la dependencia, devolvemos un mensaje claro
        raise HTTPException(
            status_code=500,
            detail="reportlab no está instalado en el contenedor. Agrega 'reportlab' a requirements.txt y reconstruye la imagen."
        )

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    x_left = 2*cm
    y = H - 2*cm

    def line(txt, size=10, dy=12):
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(x_left, y, str(txt))
        y -= dy
        if y < 2*cm:
            c.showPage()
            y = H - 2*cm

    # Encabezado
    line(f"DTE #{hdr.id}", size=14, dy=18)
    line(f"Tipo: {hdr.tipo_dte}   Folio: {hdr.folio}   Fecha: {hdr.fecha_emision}")
    line(f"Emisor: {hdr.rut_emisor} - {hdr.razon_social_emisor or ''}")
    line(f"Receptor: {hdr.rut_receptor} - {hdr.razon_social_receptor or ''}")
    line(f"Monto total: {hdr.mnt_total}", dy=16)
    line("Detalles:", size=12, dy=16)

    # Cabecera de tabla
    line("Línea | TipoCod | Código | Nombre | Cantidad | Precio | Monto", size=10, dy=14)

    # Filas
    for d in hdr.detalles:
        # compactar para que quepa en una línea
        nombre = (d.nombre_item or "")[:30]
        linea = (
            f"{d.nro_linea or ''} | {d.tipo_codigo or ''} | {d.codigo or ''} | "
            f"{nombre} | {d.cantidad or ''} | {d.precio_unitario or ''} | {d.monto_item or ''}"
        )
        line(linea, size=9, dy=12)

    c.showPage()
    c.save()
    buf.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="dte_{hdr.id}.pdf"'}
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)

# Procesa masivamente XMLs en /app/uploads que aún no existan en 'files'
@router.post("/parse_all")
def parse_all_xmls(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(require_role("CONTRIBUTOR"))
):
    with EtlRun(db, job="manual_parse_all", source="ui") as run:
        # Descubre XMLs
        xmls = [f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".xml")]
        to_process = []
        for fname in xmls:
            exists = db.query(FileModel.id).filter(FileModel.filename == fname).first()
            if not exists:
                rec = FileModel(filename=fname, uploader_id=user.id)
                db.add(rec); db.flush()
                to_process.append((rec.id, fname))
        db.commit()

        run.incr(files_total=len(to_process))
        processed = []
        for file_id, fname in to_process:
            path = os.path.join(UPLOAD_DIR, fname)
            if not os.path.exists(path):
                continue
            rec = db.get(FileModel, file_id)
            try:
                header_ids = parse_and_store_xml(rec, path, db, run_id=run.run_id)
                processed.append(file_id)
                run.incr(files_ok=1, headers_inserted=len(header_ids))
                if header_ids:
                    details_count = db.query(DteDetail).filter(DteDetail.header_id.in_(header_ids)).count()
                    run.incr(details_inserted=details_count)
                    run.incr(dq_violations=run.count_dq_for_headers(header_ids))
            except Exception as e:
                run.incr(files_failed=1)
                run.add_error(where="parse_all", message=str(e), file_id=rec.id)

        # Resumen y auditoría
        n_headers = db.query(func.count(DteHeader.id)).scalar()
        audit_action(db, getattr(user, "email", None), "parse_all",
                     resource="file", resource_id=None,
                     extra={"created_files": processed, "total_headers_now": int(n_headers)})

        return {"ok": True, "new_files": processed, "total_headers": int(n_headers)}
