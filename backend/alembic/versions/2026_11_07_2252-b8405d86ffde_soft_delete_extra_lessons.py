"""soft delete extra lessons

Видалений додатковий урок вчителя лишається рядком з `deleted_at` (надгробок): запізнілий
повтор створення з тим самим `id` отримує 410, а не воскрешає урок.

Downgrade видаляє такі рядки остаточно (інакше без колонки вони знову стали б уроками
в розкладі); надгробки при цьому втрачаються.

Revision ID: b8405d86ffde
Revises: c930d9500c52
Create Date: 2026-11-07 22:52:05.124838+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8405d86ffde"
down_revision: str | Sequence[str] | None = "c930d9500c52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "schedule_override", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM schedule_override WHERE deleted_at IS NOT NULL")
    op.drop_column("schedule_override", "deleted_at")
