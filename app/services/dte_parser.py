from datetime import datetime
from xml.etree import ElementTree as ET
from sqlalchemy.orm import Session
from app.models.dte import DteHeader, DteDetail
from app.models.file import File as FileModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text  
import logging
log = logging.getLogger(__name__)

SII_NS = {"sii": "http://www.sii.cl/SiiDte"}

def _findtext(node, path, default=None, ns=SII_NS):
    el = node.find(path, ns)
    if el is None:
        #fallback para el xml del test: mismo path pero sin prefijo "sii:"
        el = node.find(path.replace("sii:", ""))
    return (el.text.strip() if el is not None and el.text is not None else default)

def _to_int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return None

def _to_float(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None

def _to_date(v):
    try:
        return datetime.strptime(v.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def _iter_documentos(root):
    """
    Soporta:
      <Documento>...</Documento>                (sin namespace)  
      <DTE><Documento>...</Documento></DTE>     (con namespace)
      <EnvioDTE><SetDTE><DTE><Documento>...</Documento></DTE>...</SetDTE></EnvioDTE>
    """
    # si la raiz ya es documento (con o sin ns)
    if root.tag.rsplit("}", 1)[-1] == "Documento":
        yield root
        return

    yielded = False

    # documento con namespace SII
    for doc in root.findall(".//sii:Documento", SII_NS):
        yielded = True
        yield doc

    # fallback: documento sin namespace en cualquier nivel
    if not yielded:
        for el in root.iter():
            if el.tag.rsplit("}", 1)[-1] == "Documento":
                yield el

def _dq_after_insert(db: Session, header_id: int, run_id=None) -> None:
    """Inserta violaciones DQ básicas para el header recién cargado."""
    rid = str(run_id) if run_id else None

    # DQ1: cantidad > 0 y precio >= 0
    db.execute(text("""
        INSERT INTO dq_violations(run_id, rule_id, entity, entity_id, message)
        SELECT :rid, r.id, 'detail', d.id, 'cantidad<=0 o precio<0'
        FROM dte_details d
        JOIN dq_rules r ON r.code='DQ1'
        WHERE d.header_id = :hid
          AND (COALESCE(d.cantidad,0) <= 0 OR COALESCE(d.precio_unitario,0) < 0)
    """), {"rid": rid, "hid": header_id})

    # DQ2: monto = qty*precio
    db.execute(text("""
        INSERT INTO dq_violations(run_id, rule_id, entity, entity_id, message)
        SELECT :rid, r.id, 'detail', d.id, 'monto != qty*precio'
        FROM dte_details d
        JOIN dq_rules r ON r.code='DQ2'
        WHERE d.header_id = :hid
          AND ABS(COALESCE(d.monto_item,0)::numeric - (COALESCE(d.cantidad,0)::numeric * COALESCE(d.precio_unitario,0)::numeric)) > 1
    """), {"rid": rid, "hid": header_id})

    # DQ4: fecha de emision fuera de rango razonable
    db.execute(text("""
        INSERT INTO dq_violations(run_id, rule_id, entity, entity_id, message)
        SELECT :rid, r.id, 'header', h.id, 'fecha_emision fuera de rango'
        FROM dte_headers h
        JOIN dq_rules r ON r.code='DQ4'
        WHERE h.id = :hid
          AND (h.fecha_emision < DATE '2000-01-01' OR h.fecha_emision > (NOW() + INTERVAL '1 day')::date)
    """), {"rid": rid, "hid": header_id})

def parse_and_store_xml(file_rec: FileModel, file_path: str, db: Session, run_id=None) -> list[int]:
    """
    Parsea un XML DTE y persiste en dte_headers/dte_details.
    Retorna lista de ids de headers creados.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()
    header_ids = []

    for doc in _iter_documentos(root):
        enc = doc.find("sii:Encabezado", SII_NS) or doc.find("Encabezado")
        if enc is None:
            continue

        # parse campos encabezado
        tipo_dte = _to_int(_findtext(enc, "sii:IdDoc/sii:TipoDTE"))
        folio = _to_int(_findtext(enc, "sii:IdDoc/sii:Folio"))
        fch_emis = _to_date(_findtext(enc, "sii:IdDoc/sii:FchEmis"))

        rut_emisor = _findtext(enc, "sii:Emisor/sii:RUTEmisor")
        rz_emisor  = (_findtext(enc, "sii:Emisor/sii:RznSocEmisor") or _findtext(enc, "sii:Emisor/sii:RznSoc"))
        rut_recep  = _findtext(enc, "sii:Receptor/sii:RUTRecep") 
        rz_recep   = (_findtext(enc, "sii:Receptor/sii:RznSocRecep") or _findtext(enc, "sii:Receptor/sii:RznSoc"))

        mnt_neto   = _to_int(_findtext(enc, "sii:Totales/sii:MntNeto"))
        iva        = _to_int(_findtext(enc, "sii:Totales/sii:IVA"))
        mnt_total  = _to_int(_findtext(enc, "sii:Totales/sii:MntTotal"))

        # ya existe?
        existing = (db.query(DteHeader.id).filter_by(tipo_dte=tipo_dte, folio=folio, rut_emisor=rut_emisor).scalar())
        if existing:
            # no reinserta
            header_ids.append(existing)
            continue

        # insertar header
        header = DteHeader(
            tipo_dte=tipo_dte,
            folio=folio,
            fecha_emision=fch_emis,
            rut_emisor=rut_emisor,
            rut_receptor=rut_recep,
            razon_social_emisor=rz_emisor,
            razon_social_receptor=rz_recep,
            mnt_neto=mnt_neto,
            iva=iva,
            mnt_total=mnt_total,
            file_id=file_rec.id,
        )

        try:
            db.add(header)
            db.flush()  # tener header.id

        except IntegrityError:
            # Carrera: alguien insertó el mismo header justo ahora
            db.rollback()
            header = (db.query(DteHeader)
                        .filter_by(tipo_dte=tipo_dte, folio=folio, rut_emisor=rut_emisor)
                        .one())
            header_ids.append(header.id)
            # No reinsertamos detalles
            continue

        # Detalles
        for det in (doc.findall("sii:Detalle", SII_NS) or doc.findall("Detalle")):
            nrolin   = _to_int(_findtext(det, "sii:NroLinDet"))
            nombre   = _findtext(det, "sii:NmbItem")

            tipo_codigo = _findtext(det, "sii:CdgItem/sii:TpoCodigo")
            codigo      = _findtext(det, "sii:CdgItem/sii:VlrCodigo")

            qty      = _to_float(_findtext(det, "sii:QtyItem"))
            precio   = _to_float(_findtext(det, "sii:PrcItem"))
            monto    = _to_int(_findtext(det, "sii:MontoItem"))

            # fallback, si no hay DscItem, usa el nombre
            desc     = _findtext(det, "sii:DscItem") or nombre
            # fallback de precio/cantiadad ya que algunos vienen sin uno de los dos
            if precio is None and qty not in (None, 0) and monto is not None:
                precio = round(monto / qty, 2)
            if qty is None and precio not in (None, 0) and monto is not None:
                qty = round(monto / precio, 6)

            db.add(DteDetail(
                header_id=header.id,
                nro_linea=nrolin,
                tipo_codigo=tipo_codigo,
                codigo=codigo,
                nombre_item=nombre,
                cantidad=qty,
                descripcion=desc,   
                precio_unitario=precio,
                monto_item=monto
            ))
        
        #Asegura que los detalles queden en el buffer para que DQ pueda verlos
        db.flush()

        # Hook DQ para no romper el ETL por DQ
        try:
            with db.begin_nested():
                _dq_after_insert(db, header.id, run_id=run_id)
        except Exception as e:
            log.warning("DQ hook failed for header %s: %s", header.id, e)

        header_ids.append(header.id)

    db.commit()
    return header_ids

