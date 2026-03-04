from sqlalchemy.orm import Session
from app.models.role import Role
from app.models.dq import DqRule

def ensure_roles(db: Session) -> None:
    for name in ("READER", "CONTRIBUTOR"):
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name))
    db.commit()

def ensure_dq_rules(db: Session) -> None:
    rules = [
        ("DQ1", "ERROR", "detail", "cantidad<=0 o precio<0"),
        ("DQ2", "WARN",  "detail", "monto != qty*precio"),
        ("DQ4", "WARN",  "header", "fecha_emision fuera de rango"),
        # extra para consistencia general:
        ("DQ3", "ERROR", "header", "suma(detalle) != total"),
    ]
    for code, level, entity, desc in rules:
        if not db.query(DqRule).filter(DqRule.code == code).first():
            db.add(DqRule(code=code, level=level, entity=entity, description=desc))
    db.commit()
