from pydantic import BaseModel, EmailStr, ConfigDict

class UserOut(BaseModel):
    email: EmailStr
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)
