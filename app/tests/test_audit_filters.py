from app.models.audit import AuditLog

def test_audit_filters(client, db):
    db.add_all([
        AuditLog(user="a@a.com", path="/home", method="GET", status=200),
        AuditLog(user="b@b.com", path="/dq/violations", method="GET", status=200),
    ])
    db.commit()

    r = client.get("/audit")
    assert r.status_code == 200
    assert "Auditoría" in r.text or "Accesos" in r.text

    # status vacío no debe romper (422)
    r = client.get("/audit?user=&path=&method=GET&status=&date_from=&date_to=")
    assert r.status_code == 200
