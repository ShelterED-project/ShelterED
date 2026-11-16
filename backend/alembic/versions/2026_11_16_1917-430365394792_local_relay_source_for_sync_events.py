"""local relay source for sync events

`sync_event.source = 'local'`: відмітки переклички учнів, які локальний сервер укриття
(ноутбук вчителя) пересилає в `POST /sync/events` (`relayed_by` = вчитель). Нових даних про
дітей немає.

Downgrade: рядки `source = 'local'` стають `'online'` (подію не видаляємо — це відмітка учня;
`relayed_by` лишається, тож ретрансляцію ще видно).

Revision ID: 430365394792
Revises: a66996138f87
Create Date: 2026-11-16 19:17:27.390877+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "430365394792"
down_revision: str | Sequence[str] | None = "a66996138f87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f("ck_sync_event_source"), "sync_event", type_="check")
    op.create_check_constraint("source", "sync_event", "source IN ('online', 'qr', 'local')")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE sync_event SET source = 'online' WHERE source = 'local'")
    op.drop_constraint(op.f("ck_sync_event_source"), "sync_event", type_="check")
    op.create_check_constraint("source", "sync_event", "source IN ('online', 'qr')")
