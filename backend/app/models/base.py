import datetime as dt
import uuid

from sqlalchemy import MetaData, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Явні імена індексів і обмежень: без них Postgres генерує свої, і міграції
# (особливо downgrade) не можуть надійно на них посилатися.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовий клас усіх SQLAlchemy-моделей; його metadata бачить Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # str -> text (без VARCHAR), час -> timestamptz (завжди UTC).
    type_annotation_map = {
        str: Text,
        uuid.UUID: UUID(as_uuid=True),
        dt.datetime: TIMESTAMP(timezone=True),
    }


def uuid_pk() -> Mapped[uuid.UUID]:
    """PK-uuid. Id, які створює сервер, поки uuid4; v7 — коли погодимо бібліотеку.

    Клієнтські id сервер приймає як є, тож default спрацьовує лише для серверних рядків.
    """
    return mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
