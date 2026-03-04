import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from pypdf import PdfReader

from sqlalchemy.orm import Session
from app.models.dte import DteHeader
from app.models.file import File as FileModel

# --- Utiles de parsing -------------------------------------------------

def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s, flags=re.S).strip()

def _find(pattern: str, text: str, flags=re.I) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None

def _parse_chilean_money(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    s = s.replace("$", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return int(round(float(s)))
    except Exception:
        return None

def _parse_fecha(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("\\", "-").replace("/", "-")
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%m-%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None

def _detect_tipo(text: str) -> Optional[int]:
    t = text.lower()
    if "nota de crédito" in t or "nota de credito" in t:
        return 61
    if "nota de débito" in t or "nota de debito" in t:
        return 56
    if "boleta" in t:
        return 39  
    if "factura" in t:
        if re.search(r"factura.*exenta|exenta.*factura", t, re.I | re.S):
            return 34
        return 33
    return None

def _read_text_from_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".htm", ".html"):
        html = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "lxml")
        return _norm_text(soup.get_text(" "))
    elif ext == ".pdf":
        reader = PdfReader(str(path))
        pages = [p.extract_text() or "" for p in reader.pages]
        return _norm_text("\n".join(pages))
    else:
        return _norm_text(path.read_text(encoding="utf-8", errors="ignore"))

def _parse_header_fields(text: str) -> dict:
    # patrones tipicos en DTE chilenos (HTML/PDF)
    tipo = _detect_tipo(text)
    folio = _find(r"\b(?:Folio|N[°º]|Nro\.?)\s*[:#]?\s*(\d{3,12})", text)
    rut_emisor = _find(r"RUT\s*(?:Emisor|Empresa)\s*[:#]?\s*([\dkK\.\-]+)", text)
    rut_recep  = _find(r"RUT\s*(?:Receptor|Cliente)\s*[:#]?\s*([\dkK\.\-]+)", text) or \
                 _find(r"RUT\s*(?:Destinatario)\s*[:#]?\s*([\dkK\.\-]+)", text)
    fecha = _find(r"(?:Fecha(?:\s*Emisi[oó]n)?|FchEmis)\s*[:#]?\s*([0-9]{2,4}[\/\-][0-9]{1,2}[\/\-][0-9]{1,2})", text)
    total = _find(r"(?:Monto\s*Total|Total\s*(?:a\s*Pagar)?|MntTotal)\s*[:#]?\s*\$?\s*([\d\.\,]+)", text)

    return {
        "tipo_dte": tipo,
        "folio": int(folio) if folio else None,
        "rut_emisor": rut_emisor,
        "rut_receptor": rut_recep,
        "fecha_emision": _parse_fecha(fecha).date() if _parse_fecha(fecha) else None,
        "mnt_total": _parse_chilean_money(total),
    }

# --- API principal ------------------------------------------------------

def ingest_file_to_dte(db: Session, file_id: int, upload_dir: str = "app/uploads") -> DteHeader:
    f: FileModel | None = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not f:
        raise ValueError(f"Archivo id={file_id} no existe")

    path = Path(upload_dir) / f.filename
    if not path.exists():
        raise ValueError(f"Archivo físico no encontrado: {path}")

    text = _read_text_from_file(path)
    fields = _parse_header_fields(text)

    header = DteHeader(
        file_id=file_id,
        tipo_dte=fields["tipo_dte"],
        folio=fields["folio"],
        rut_emisor=fields["rut_emisor"],
        rut_receptor=fields["rut_receptor"],
        fecha_emision=fields["fecha_emision"],
        mnt_total=fields["mnt_total"],
    )
    db.add(header)
    db.commit()
    db.refresh(header)
    return header
