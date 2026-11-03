"""Widen clock skew, nulls not distinct alert key

Revision ID: a40c36c2b02b
Revises: f2bb4cfc37c4
Create Date: 2026-11-01 10:25:38.686065+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a40c36c2b02b"
down_revision: str | Sequence[str] | None = "f2bb4cfc37c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(op.f("uq_alert_event_source_external_school"), "alert_event", type_="unique")
    op.create_index(
        "uq_alert_event_source_external_school",
        "alert_event",
        ["source", "external_id", "school_id"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.alter_column(
        "sync_event",
        "clock_skew_ms",
        existing_type=sa.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "sync_event",
        "clock_skew_ms",
        existing_type=sa.BigInteger(),
        type_=sa.INTEGER(),
        existing_nullable=True,
    )
    op.drop_index(
        "uq_alert_event_source_external_school",
        table_name="alert_event",
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_unique_constraint(
        op.f("uq_alert_event_source_external_school"),
        "alert_event",
        ["source", "external_id", "school_id"],
        postgresql_nulls_not_distinct=False,
    )
