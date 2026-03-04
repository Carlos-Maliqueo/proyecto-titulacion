from sqlalchemy import String, Integer, ForeignKey, Numeric, Date, DateTime, func, UniqueConstraint, Index, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base_class import Base
from typing import Optional
from decimal import Decimal

class DteHeader(Base):
    __tablename__ = "dte_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"), nullable=True, index=True)

    tipo_dte: Mapped[int] = mapped_column(Integer, index=True) #39: boletas, 33: facturas, notas de credito: 61 y notas de debito:56
    folio: Mapped[int] = mapped_column(Integer, index=True)
    fecha_emision: Mapped[Date] = mapped_column(Date, index=True)

    rut_emisor: Mapped[str] = mapped_column(String(16), index=True)
    razon_social_emisor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    rut_receptor: Mapped[str] = mapped_column(String(16), index=True)
    razon_social_receptor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    mnt_neto: Mapped[Numeric] = mapped_column(Numeric(18, 2))
    iva: Mapped[Numeric] = mapped_column(Numeric(18, 2))
    mnt_total: Mapped[Numeric] = mapped_column(Numeric(18, 2), index=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    detalles: Mapped[list["DteDetail"]] = relationship(back_populates="header", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tipo_dte", "folio", "rut_emisor", name="uq_dte_headers_tipo_folio_emisor"),
        Index("ix_dte_headers_fecha", "fecha_emision"),
    )


class DteDetail(Base):
    __tablename__ = "dte_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    header_id: Mapped[int] = mapped_column(ForeignKey("dte_headers.id"), index=True)

    nro_linea: Mapped[int] = mapped_column(Integer, nullable=True)
    tipo_codigo: Mapped[str] = mapped_column(String(20), nullable=True)
    nombre_item: Mapped[str] = mapped_column(String(255), nullable=True)
    codigo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    descripcion: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cantidad: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=True)
    precio_unitario: Mapped[Numeric] = mapped_column(Numeric(18, 6), nullable=True)
    monto_item: Mapped[Numeric] = mapped_column(Numeric(18, 2), index=True, nullable=True)

    header: Mapped[DteHeader] = relationship(back_populates="detalles")

    ai_category    = Column(String(50))
    ai_subcategory = Column(String(60))
    ai_brand       = Column(String(60))
    ai_attrs       = Column(JSONB)            # {dimension:{w:60,h:46}, color:"Cromo", material:"Inox", ...}
    ai_confidence  = Column(Numeric(5,2))
    ai_version     = Column(String(20))

    __table_args__ = (
        UniqueConstraint('header_id', 'nro_linea', name='uq_dte_details_header_line'),
        Index('ix_dte_details_header_id', 'header_id'),
    )