from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
import xml.etree.ElementTree as ET

from app.deps import get_db, require_role
from app.models.dte import DteHeader, DteDetail
from app.models.file import File as FileModel
from app.services.audit import audit_action

router = APIRouter(prefix="/dte", tags=["dte"])

# Utilidad para buscar por nombre de etiqueta sin preocuparnos del namespace

def _find_first_text_any(root: ET.Element, tag: str) -> str | None:
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.endswith(tag):
            return (el.text or "").strip() or None
    return None

def _findall_any(root: ET.Element, tag: str) -> list[ET.Element]:
    out = []
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.endswith(tag):
            out.append(el)
    return out

def _to_decimal(s: str | None) -> Decimal:
    try:
        return Decimal(s.replace(",", ".")) if s is not None else Decimal(0)
    except Exception:
        return Decimal(0)

def _to_int(s: str | None) -> int:
    try:
        return int(s) if s is not None else 0
    except Exception:
        return 0
    
def parse_dte(xml_bytes: bytes) -> tuple[dict, list[dict]]:
    root = ET.fromstring(xml_bytes)

    tipo = _find_first_text_any(root, "TipoDTE") or ""
    folio = _find_first_text_any(root, "Folio") or ""
    fch = _find_first_text_any(root, "FchEmis") or _find_first_text_any(root, "FechaEmision")
    fecha_emision = datetime.strptime(fch, "%Y-%m-%d").date() if fch else datetime.utcnow().date()

    rut_emisor = _find_first_text_any(root, "RUTEmisor") or ""
    rznsoc_emisor = _find_first_text_any(root, "RznSoc") or ""

    rut_receptor = _find_first_text_any(root, "RUTRecep") or ""
    rznsoc_receptor = _find_first_text_any(root, "RznSocRecep") or ""

    mnt_neto = _to_decimal(_find_first_text_any(root, "MntNeto"))
    iva = _to_decimal(_find_first_text_any(root, "IVA"))
    mnt_total = _to_decimal(_find_first_text_any(root, "MntTotal"))

    # Detalle(s)
    detalles = []
    for det in _findall_any(root, "Detalle"):
        n_linea = _to_int(_find_first_text_any(det, "NroLinDet"))
        codigo = (_find_first_text_any(det, "CdgItem") or "") + (":" + (_find_first_text_any(det, "VlrCodigo") or "") if _find_first_text_any(det, "VlrCodigo") else "")
        desc = _find_first_text_any(det, "NmbItem") or ""
        qty = _to_decimal(_find_first_text_any(det, "QtyItem"))
        punit = _to_decimal(_find_first_text_any(det, "PrcItem"))
        monto = _to_decimal(_find_first_text_any(det, "MontoItem"))
        detalles.append({
            "n_linea": n_linea,
            "codigo": codigo or None,
            "descripcion": desc,
            "cantidad": qty,
            "precio_unit": punit,
            "monto_item": monto,
    })
        
    header = {
        "tipo_dte": tipo,
        "folio": folio,
        "fecha_emision": fecha_emision,
        "rut_emisor": rut_emisor,
        "rznsoc_emisor": rznsoc_emisor,
        "rut_receptor": rut_receptor,
        "rznsoc_receptor": rznsoc_receptor,
        "mnt_neto": mnt_neto,
        "iva": iva,
        "mnt_total": mnt_total,
    }
    return header, detalles

@router.get("")
def list_dte(db: Session = Depends(get_db)):
    q = db.query(DteHeader).order_by(DteHeader.id.desc()).all()
    return [
        {
            "id": h.id,
            "tipo": h.tipo_dte,
            "folio": h.folio,
            "fecha": h.fecha_emision.isoformat(),
            "emisor": f"{h.rut_emisor} - {h.rznsoc_emisor}",
            "receptor": f"{h.rut_receptor} - {h.rznsoc_receptor}",
            "total": str(h.mnt_total),
        }
        for h in q
    ]

# inventario (conteo por tipo)
@router.get("/stats/types", response_model=None)
def dte_type_stats(db: Session = Depends(get_db), _=Depends(require_role("READER","CONTRIBUTOR"))):
    from sqlalchemy import func
    
    rows = (db.query(DteHeader.tipo_dte, func.count().label("n"), func.sum(DteHeader.mnt_total).label("monto"))
              .group_by(DteHeader.tipo_dte)
              .order_by(DteHeader.tipo_dte)
              .all())
    
    return [
        {
            "tipo_dte": t, 
            "n": int(n or 0), 
            "monto": float(m or 0)
        } 
        for (t,n,m) in rows
    ]

# diccionario de campos
@router.get("/schema/dictionary")
def dte_dictionary(_=Depends(require_role("READER","CONTRIBUTOR"))):
    def cols(model):
        return [
            {
                "name": c.name, 
                "type": str(c.type), 
                "nullable": c.nullable, 
                "pk": c.primary_key
            }
                
            for c in model.__table__.columns
        ]
    return {
        "dte_headers": cols(DteHeader), 
        "dte_details": cols(DteDetail)
    }

