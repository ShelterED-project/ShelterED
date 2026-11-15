"""school alert locations

Точні локації школи для тривог alerts.in.ua (uid району, громади, міста) і поля тривоги
провайдера, що ввімкнула тривогу школи, у журналі (`alert_event`). Нових даних про дітей немає.

Revision ID: a66996138f87
Revises: b8405d86ffde
Create Date: 2026-11-10 14:26:56.465422+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a66996138f87"
down_revision: str | Sequence[str] | None = "b8405d86ffde"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCATION_COLUMNS = ("alert_raion_uid", "alert_hromada_uid", "alert_city_uid")
EVENT_COLUMNS = ("location_type", "location_uid", "location_title", "alert_type")


def upgrade() -> None:
    """Upgrade schema."""
    for col in EVENT_COLUMNS:
        op.add_column("alert_event", sa.Column(col, sa.Text(), nullable=True))
    for col in LOCATION_COLUMNS:
        op.add_column("school", sa.Column(col, sa.Text(), nullable=True))
        op.create_check_constraint(f"{col}_format", "school", f"{col} ~ '^[0-9]{{1,9}}$'")
        op.create_index(
            f"ix_school_{col}",
            "school",
            [col],
            unique=False,
            postgresql_where=sa.text(f"{col} IS NOT NULL"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    for col in reversed(LOCATION_COLUMNS):
        op.drop_index(
            f"ix_school_{col}", table_name="school", postgresql_where=sa.text(f"{col} IS NOT NULL")
        )
        op.drop_constraint(f"{col}_format", "school", type_="check")
        op.drop_column("school", col)
    for col in reversed(EVENT_COLUMNS):
        op.drop_column("alert_event", col)
