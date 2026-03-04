from app.models.dq import DqRule, DqViolation
from app.models.dte import DteHeader, DteDetail

def test_dq_violations_filters(client, db):
    # regla
    rule = db.query(DqRule).filter_by(code="DQ2").first()
    if not rule:
        rule = DqRule(
            code="DQ2",
            level="WARN",
            entity="detail",
            description="monto != qty*precio",
        )
        db.add(rule); db.flush()

    # header + detail
    h = DteHeader(
        tipo_dte="33", folio="100", rut_emisor="11111111-1", razon_social_emisor="Emisor SA",
        rut_receptor="22222222-2", razon_social_receptor="Receptor SA",
        fecha_emision="2025-10-17", mnt_neto=1000, iva=190, mnt_total=1190
    )
    db.add(h); db.flush()
    d = DteDetail(header_id=h.id, nro_linea=1, tipo_codigo=None, codigo=None,
                  nombre_item="item", descripcion=None, cantidad=2, precio_unitario=600, monto_item=1200)
    db.add(d); db.flush()

    # violación a nivel detail
    v = DqViolation(rule_id=rule.id, entity="detail", entity_id=d.id, message="monto != qty*precio")
    db.add(v); db.commit()

    # listado base
    r = client.get("/dq/violations")
    assert r.status_code == 200
    assert "Data Quality" in r.text or "Violaciones" in r.text

    # filtro por code
    r = client.get("/dq/violations?code=DQ2")
    assert r.status_code == 200
    assert "DQ2" in r.text

    # filtro por header_id (debe aceptar string vacío sin 422)
    r = client.get("/dq/violations?code=DQ2&header_id=")
    assert r.status_code == 200
