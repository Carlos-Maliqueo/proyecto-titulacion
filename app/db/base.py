from app.db.base_class import Base

# se importa todos los modelos para que queden registrados en Base.metadata
from app.models.user import User
from app.models.role import Role
from app.models.file import File
from app.models.dte import DteHeader, DteDetail
from app.models.dq import DqRule, DqViolation
from app.models.audit import AuditLog
from app.models.runlog import RunLog
from app.models.dq_health import DqHealth

