# app/services/audit.py
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog

def audit_action(
    db: Session,
    user_email: Optional[str],
    action: str,
    *,
    resource: Optional[str] = None,
    resource_id: Optional[int] = None,
    extra: Optional[dict[str, Any]] = None,
    status: Optional[int] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
) -> None:
    rec = AuditLog(
        user=user_email or "-",
        path=path or f"/action/{action}",
        method=method or "POST",
        status=status or 0,
        action=action,
        resource=resource,
        resource_id=resource_id,
        extra=extra or {},
    )
    db.add(rec)
    db.commit()
