from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

class FileOut(BaseModel):
    id: int
    filename: str
    uploader_email: EmailStr | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

