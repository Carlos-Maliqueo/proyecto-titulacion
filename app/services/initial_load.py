import os
from sqlalchemy.orm import Session
from app.models.file import File as FileModel
from app.models.dte import DteDetail
from app.services.dte_parser import parse_and_store_xml
from app.services.etl_run import EtlRun

def run_initial_load(db: Session, upload_dir: str = "app/uploads") -> dict:
    with EtlRun(db, job="initial_load", source="bootstrap", note="carga inicial") as run:
        xmls = [f for f in os.listdir(upload_dir) if f.lower().endswith(".xml")]
        new_files = []
        for fname in xmls:
            if not db.query(FileModel.id).filter(FileModel.filename == fname).first():
                rec = FileModel(filename=fname, uploader_id=None)
                db.add(rec); db.flush()
                new_files.append(rec)
        db.commit()

        run.incr(files_total=len(new_files))
        processed, failed = [], []

        for rec in new_files:
            path = os.path.join(upload_dir, rec.filename)
            try:
                header_ids = parse_and_store_xml(rec, path, db, run_id=run.run_id)
                run.incr(files_ok=1, headers_inserted=len(header_ids))
                if header_ids:
                    n_det = db.query(DteDetail).filter(DteDetail.header_id.in_(header_ids)).count()
                    run.incr(details_inserted=n_det)
                    run.incr(dq_violations=run.count_dq_for_headers(header_ids))
                processed.append(rec.id)
            except Exception as e:
                run.incr(files_failed=1)
                run.add_error(where="initial_load.parse", message=str(e), file_id=rec.id)
                failed.append(rec.id)

        return {
            "files_created": [r.id for r in new_files],
            "processed": processed,
            "failed": failed,
        }
