import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class PushSubscription(TimestampMixin, Base):
    __tablename__ = "push_subscription"
    # Розсилка (subscriptions_of) і ліміт підписок шукають за користувачем.
    __table_args__ = (Index("ix_push_subscription_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    # Кілька пристроїв на користувача.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    endpoint: Mapped[str] = mapped_column(unique=True)
    p256dh: Mapped[str]
    auth: Mapped[str]
    last_success_at: Mapped[dt.datetime | None]
    failed_at: Mapped[dt.datetime | None]
