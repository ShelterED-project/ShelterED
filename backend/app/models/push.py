import datetime as dt
import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class PushSubscription(TimestampMixin, Base):
    __tablename__ = "push_subscription"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Кілька пристроїв на користувача.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    endpoint: Mapped[str] = mapped_column(unique=True)
    p256dh: Mapped[str]
    auth: Mapped[str]
    last_success_at: Mapped[dt.datetime | None]
    failed_at: Mapped[dt.datetime | None]
