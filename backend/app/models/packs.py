import datetime as dt
import uuid

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class KnowledgePack(Base):
    """Пакет «Рюкзак»: клас + дата + версія. Актуальна версія — найбільша."""

    __tablename__ = "knowledge_pack"
    __table_args__ = (
        UniqueConstraint("class_id", "pack_date", "version", name="uq_knowledge_pack_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_class.id", ondelete="CASCADE"))
    pack_date: Mapped[dt.date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    # sha256 вмісту; він же ETag.
    content_hash: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    built_at: Mapped[dt.datetime]


class KnowledgePackLesson(Base):
    __tablename__ = "knowledge_pack_lesson"

    pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_pack.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id"), primary_key=True)
    # Версія уроку на момент збірки.
    lesson_version: Mapped[int] = mapped_column(Integer)


class KnowledgePackMedia(Base):
    __tablename__ = "knowledge_pack_media"

    pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_pack.id", ondelete="CASCADE"), primary_key=True
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_asset.id"), primary_key=True
    )
