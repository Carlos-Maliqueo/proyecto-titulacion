from app.models.runlog import RunLog

def _mk_run(db, **kw):
    r = RunLog(
        run_id=kw.get("run_id","test123"),
        job=kw.get("job","manual_parse"),
        source=kw.get("source","ui"),
        status=kw.get("status","OK"),
        files_total=kw.get("files_total",3),
        files_ok=kw.get("files_ok",3),
        files_failed=kw.get("files_failed",0),
        headers_inserted=kw.get("headers_inserted",5),
        details_inserted=kw.get("details_inserted",12),
        dq_violations=kw.get("dq_violations",2),
        note=kw.get("note")
    )
    db.add(r); db.flush()
    return r

def test_runs_filters_and_detail(client, db):
    r1 = _mk_run(db, run_id="r1", job="etl_daily",  source="gosocket", status="OK")
    r2 = _mk_run(db, run_id="r2", job="manual_parse", source="ui",      status="ERROR")

    # lista sin filtros
    resp = client.get("/ops/runs")
    assert resp.status_code == 200
    assert "ETL - Runs" in resp.text

    # filtro por job
    resp = client.get("/ops/runs?job=etl_daily")
    assert resp.status_code == 200
    assert "r1" in resp.text and "r2" not in resp.text

    # filtro por status
    resp = client.get("/ops/runs?status=ERROR")
    assert resp.status_code == 200
    assert "r2" in resp.text and "r1" not in resp.text

    # detalle
    resp = client.get("/ops/runs/r1")
    assert resp.status_code == 200
    assert "Run Detail" in resp.text
    assert "r1" in resp.text
