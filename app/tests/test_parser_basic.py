from app.models.file import File as FileModel
from app.services.dte_parser import parse_and_store_xml
from app.models.dte import DteHeader, DteDetail
from app.models.dq import DqRule, DqViolation

def test_parser_parses_minimal_xml_and_triggers_dq(client, db, tmp_path):
    # 1) XML mínimo con un cálculo mal (para gatillar DQ2: monto != qty*precio)
    xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Documento>
  <Encabezado>
    <IdDoc><TipoDTE>33</TipoDTE><Folio>1001</Folio><FchEmis>2025-10-14</FchEmis></IdDoc>
    <Emisor><RUTEmisor>11111111-1</RUTEmisor><RznSoc>EMISOR SA</RznSoc></Emisor>
    <Receptor><RUTRecep>22222222-2</RUTRecep><RznSocRecep>RECEPTOR SPA</RznSocRecep></Receptor>
    <Totales><MntNeto>100</MntNeto><IVA>19</IVA><MntTotal>119</MntTotal></Totales>
  </Encabezado>
  <Detalle><NroLinDet>1</NroLinDet><NmbItem>Item A</NmbItem><QtyItem>2</QtyItem><PrcItem>50</PrcItem><MontoItem>120</MontoItem></Detalle>
</Documento>
"""
    p = tmp_path / "min.xml"
    p.write_text(xml, encoding="latin-1")

    # 2) Asegurar regla DQ (si ya existe, úsala)
    rule = db.query(DqRule).filter_by(code="DQ2").first()
    if not rule:
        rule = DqRule(code="DQ2", level="WARN", entity="detail", description="monto != qty*precio")
        db.add(rule); db.flush()

    # 3) Registrar file y parsear
    rec = FileModel(filename=str(p.name), uploader_id=None)
    db.add(rec); db.flush()

    header_ids = parse_and_store_xml(rec, str(p), db)
    assert len(header_ids) == 1

    # 4) Asserts de persistencia
    hdr = db.get(DteHeader, header_ids[0])   # evita LegacyAPIWarning
    assert hdr is not None
    assert hdr.tipo_dte == 33 and hdr.folio == 1001
    assert hdr.mnt_total == 119

    dets = db.query(DteDetail).filter_by(header_id=hdr.id).all()
    assert len(dets) == 1
    d = dets[0]
    assert d.cantidad == 2 and d.precio_unitario == 50 and d.monto_item == 120  # mismatch, gatilla DQ2

    # 5) DQ creada
    dq = (db.query(DqViolation)
            .filter(DqViolation.entity=="detail", DqViolation.entity_id==d.id)
            .all())
    assert len(dq) >= 1
