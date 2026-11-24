"""tutor explanation attempts

`tutor_explanation_attempt`: лічильник невдалих спроб згенерувати пояснення за ключем кешу
(`tutor_explanation.cache_key`), щоб beat не повторював виклики LLM для вмісту, який не
отримає пояснення. Персональних даних немає. Downgrade — лише `drop_table` (спрацьовує й на
ранній формі таблиці).

Revision ID: d4a7c1e9b562
Revises: b8e4f2a6c913
Create Date: 2026-11-24 20:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a7c1e9b562"
down_revision: str | Sequence[str] | None = "b8e4f2a6c913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tutor_explanation_attempt",
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "last_attempt_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key", name=op.f("pk_tutor_explanation_attempt")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tutor_explanation_attempt")
