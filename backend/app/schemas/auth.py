import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# Імена: без зайвих пробілів, 1–50 символів (як CHECK у БД).
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
# Простий формат email (email-validator не підключаємо); CITEXT у БД ігнорує регістр.
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
Pin = Annotated[str, StringConstraints(pattern=r"^\d{4,6}$")]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Час життя access-токена, секунди")


class AuthorizeRequest(BaseModel):
    email: Email
    password: str
    code_challenge: str = Field(min_length=43, max_length=128)
    code_challenge_method: Literal["S256"]
    client_id: str
    redirect_uri: str | None = None


class AuthorizeResponse(BaseModel):
    code: str


class TokenRequest(BaseModel):
    """Тіло `POST /auth/token`: JSON або `application/x-www-form-urlencoded` (RFC 6749)."""

    grant_type: Literal["authorization_code", "refresh_token"]
    code: str | None = None
    code_verifier: str | None = None
    client_id: str | None = None
    redirect_uri: str | None = None
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str


class StudentJoinRequest(BaseModel):
    join_code: str
    display_name: Name
    last_name: Name
    pin: Pin = Field(description="4–6 цифр")


class UserOut(BaseModel):
    id: uuid.UUID
    role: str
    display_name: str
    last_name: str | None
    school_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class AdminCreateUserRequest(BaseModel):
    email: Email
    display_name: Name
    last_name: Name | None = None
    role: Literal["teacher", "parent", "admin"]
    password: str = Field(min_length=8, max_length=128, description="Початковий пароль")


class ParentLinkCodeResponse(BaseModel):
    code: str
    expires_at: dt.datetime


class ParentLinkRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class ParentLinkResponse(BaseModel):
    child_id: uuid.UUID
    display_name: str
    last_name: str | None
