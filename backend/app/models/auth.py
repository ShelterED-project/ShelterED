import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class RefreshToken(Base):
    """Refresh-токен: у БД лише SHA-256 хеш. Токени однієї ротації мають спільний family_id."""

    __tablename__ = "refresh_token"
    __table_args__ = (Index("ix_refresh_token_family_id", "family_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    family_id: Mapped[uuid.UUID]
    token_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[dt.datetime]
    revoked_at: Mapped[dt.datetime | None]
    # Токен, яким цей замінено при ротації.
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refresh_token.id"))
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    user_agent: Mapped[str | None]


class AuthCode(Base):
    """Одноразовий код авторизації OAuth 2.0 (PKCE), живе ~60 с."""

    __tablename__ = "auth_code"

    id: Mapped[uuid.UUID] = uuid_pk()
    code_hash: Mapped[str] = mapped_column(unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    code_challenge: Mapped[str]
    client_id: Mapped[str]
    redirect_uri: Mapped[str | None]
    expires_at: Mapped[dt.datetime]
    used_at: Mapped[dt.datetime | None]


class ParentLinkCode(Base):
    """Одноразовий код, яким батьки прив'язуються до дитини."""

    __tablename__ = "parent_link_code"

    id: Mapped[uuid.UUID] = uuid_pk()
    code_hash: Mapped[str] = mapped_column(unique=True)
    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    expires_at: Mapped[dt.datetime]
    used_at: Mapped[dt.datetime | None]
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
