from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class File(Base):
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    uploader = relationship("User")
