import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Імена: без зайвих пробілів, 1–50 символів (як CHECK у БД).
# Без керівних символів (\x00-\x1f).
Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=50, pattern=r"^[^\x00-\x1f]+$"
    ),
]
# Простий формат email (email-validator не підключаємо); CITEXT у БД ігнорує регістр.
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=254,
        pattern=r"^[^@\s\x00-\x1f]+@[^@\s\x00-\x1f]+\.[^@\s\x00-\x1f]+$",
    ),
]
Pin = Annotated[str, StringConstraints(pattern=r"^[0-9]{4,6}$")]
JoinCode = Annotated[str, StringConstraints(max_length=64, pattern=r"^[^\x00-\x1f]+$")]

USER_ID = "0192f0a0-0000-7000-8000-0000000000bb"
SCHOOL_ID = "0192f0a0-0000-7000-8000-0000000000aa"
CHILD_ID = "0192f0a0-0000-7000-8000-0000000000cc"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Час життя access-токена, секунди")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "q8xZ3...Rk",
                    "token_type": "bearer",
                    "expires_in": 900,
                }
            ]
        }
    )


class AuthorizeRequest(BaseModel):
    email: Email
    password: str = Field(max_length=128)
    code_challenge: str = Field(pattern=r"^[A-Za-z0-9_-]{43,128}$")
    code_challenge_method: Literal["S256"]
    client_id: str = Field(max_length=64)
    redirect_uri: str | None = Field(default=None, max_length=2048)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "teacher@school.ua",
                    "password": "correct-horse-battery",
                    "code_challenge": CHALLENGE,
                    "code_challenge_method": "S256",
                    "client_id": "sheltered-pwa",
                }
            ]
        }
    )


class AuthorizeResponse(BaseModel):
    code: str

    model_config = ConfigDict(json_schema_extra={"examples": [{"code": "Xb9...Qw"}]})


class TokenRequest(BaseModel):
    """Тіло `POST /auth/token`: JSON або `application/x-www-form-urlencoded` (RFC 6749)."""

    grant_type: Literal["authorization_code", "refresh_token"]
    code: str | None = None
    code_verifier: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._~-]{43,128}$")
    client_id: str | None = None
    redirect_uri: str | None = Field(default=None, max_length=2048)
    refresh_token: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "grant_type": "authorization_code",
                    "code": "Xb9...Qw",
                    "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
                    "client_id": "sheltered-pwa",
                },
                {"grant_type": "refresh_token", "refresh_token": "q8xZ3...Rk"},
            ]
        }
    )


class LogoutRequest(BaseModel):
    refresh_token: str

    model_config = ConfigDict(json_schema_extra={"examples": [{"refresh_token": "q8xZ3...Rk"}]})


class StudentJoinRequest(BaseModel):
    join_code: JoinCode
    display_name: Name
    last_name: Name
    pin: Pin = Field(description="4–6 цифр")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "join_code": "K7M2XQ9P",
                    "display_name": "Іван",
                    "last_name": "Петренко",
                    "pin": "1234",
                }
            ]
        }
    )


class UserOut(BaseModel):
    id: uuid.UUID
    role: str
    display_name: str
    last_name: str | None
    school_id: uuid.UUID | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": USER_ID,
                    "role": "teacher",
                    "display_name": "Олена",
                    "last_name": "Іваненко",
                    "school_id": SCHOOL_ID,
                }
            ]
        },
    )


class MeOut(UserOut):
    """Поточний користувач. Для учня `class_id` -- його клас (потрібен, щоб запитати «Рюкзак»);
    для інших ролей `null`."""

    class_id: uuid.UUID | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": USER_ID,
                    "role": "student",
                    "display_name": "Іван",
                    "last_name": "Петренко",
                    "school_id": SCHOOL_ID,
                    "class_id": "0192f0a0-0000-7000-8000-000000000001",
                }
            ]
        },
    )


class AdminCreateUserRequest(BaseModel):
    email: Email
    display_name: Name
    last_name: Name | None = None
    role: Literal["teacher", "parent", "admin"]
    password: str = Field(min_length=8, max_length=128, description="Початковий пароль")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "teacher@school.ua",
                    "display_name": "Олена",
                    "last_name": "Іваненко",
                    "role": "teacher",
                    "password": "initial-password-123",
                }
            ]
        }
    )


class ParentLinkCodeResponse(BaseModel):
    code: str
    expires_at: dt.datetime

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"code": "P4Q7Z2", "expires_at": "2026-11-12T10:00:00Z"}]}
    )


class ParentLinkRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)

    model_config = ConfigDict(json_schema_extra={"examples": [{"code": "P4Q7Z2"}]})


class ParentLinkResponse(BaseModel):
    child_id: uuid.UUID
    display_name: str
    last_name: str | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"child_id": CHILD_ID, "display_name": "Іван", "last_name": "Петренко"}]
        }
    )
