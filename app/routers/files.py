import urllib
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.deps import get_current_user, require_role, get_db
from app.models.file import File as FileModel
from app.schemas.file import FileOut
from app.services.audit import audit_action
import os

router = APIRouter(prefix="/files", tags=["files"])
UPLOAD_DIR = "app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("", response_model=list[FileOut])
def list_files(db: Session = Depends(get_db), user = Depends(get_current_user)):
    # proteger el listado, se mantiene el require de usuario autenticado
    return db.query(FileModel).order_by(FileModel.created_at.desc()).all()
    
    # # Serialización explícita para exponer uploader_email
    # return [
    #     FileOut(
    #         id=r.id,
    #         filename=r.filename,
    #         uploader_email=getattr(getattr(r, "uploader", None), "email", None),
    #         created_at=r.created_at,
    #     )
    #     for r in recs
    # ]

@router.post("/upload")
def upload_file(
    request: Request,
    up: UploadFile = File(...),
    user = Depends(require_role("CONTRIBUTOR")),
    db: Session = Depends(get_db)
):
    dest = os.path.join(UPLOAD_DIR, up.filename)
    with open(dest, "wb") as f:
        f.write(up.file.read())

    rec = FileModel(filename=up.filename, uploader_id=user.id)
    db.add(rec)
    db.commit()
    db.refresh(rec)

    audit_action(
        db,
        getattr(user, "email", None),
        "file_upload",
        resource="file",
        resource_id=rec.id,
        extra={"filename": rec.filename},
        status=201
    )

    # Si el cliente espera HTML (caso formulario del navegador), redirigimos a /home
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        fn = urllib.parse.quote(rec.filename)
        return RedirectResponse(url=f"/home?uploaded=1&fn={fn}", status_code=303)

    # Si es API (JSON), devolvemos payload
    return {"id": rec.id, "filename": rec.filename}


# @router.post("/upload")
# def upload_file(
#     up: UploadFile = File(...),
#     user = Depends(require_role("CONTRIBUTOR")),
#     db: Session = Depends(get_db)
# ):
#     dest = os.path.join(UPLOAD_DIR, up.filename)
#     with open(dest, "wb") as f:
#         f.write(up.file.read())
#     rec = FileModel(filename=up.filename, uploader_id=user.id)
#     db.add(rec); db.commit(); db.refresh(rec)
#     return {"id": rec.id, "filename": rec.filename}
