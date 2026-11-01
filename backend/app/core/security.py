import base64
import datetime as dt
import hashlib
import secrets
import uuid

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.errors import AppError

ALGORITHM = "HS256"

# Argon2id з рекомендованими параметрами pwdlib.
_hasher = PasswordHash.recommended()
# Хеш-пустушка: перевірка неіснуючого користувача займає стільки ж часу, що й справжня.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")

# Без 0/O/1/I/L: код диктують і переписують вручну.
LINK_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LINK_CODE_LENGTH = 8


def hash_secret(value: str) -> str:
    """Хеш пароля або PIN (argon2)."""
    return _hasher.hash(value)


def verify_secret(value: str, hashed: str | None) -> bool:
    if hashed is None:
        _hasher.verify(value, _DUMMY_HASH)
        return False
    return _hasher.verify(value, hashed)


def hash_token(token: str) -> str:
    """SHA-256 для токенів і кодів з високою ентропією: у БД лише хеш."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def new_link_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))


def normalize_link_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_pkce(verifier: str, challenge: str) -> bool:
    return secrets.compare_digest(pkce_challenge(verifier), challenge)


def create_access_token(user_id: uuid.UUID, role: str, settings: Settings) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_ttl_min),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "role", "exp", "iat", "jti", "type"]},
        )
        if claims["type"] != "access":
            raise jwt.InvalidTokenError("wrong token type")
        uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise AppError("UNAUTHORIZED", "Invalid or expired token", status_code=401) from exc
    return claims
