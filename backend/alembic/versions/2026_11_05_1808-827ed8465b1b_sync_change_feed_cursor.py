"""sync change feed cursor

Revision ID: 827ed8465b1b
Revises: 0edf076a683a
Create Date: 2026-11-05 18:08:16.480454+00:00

Стрічка змін `GET /sync/changes` (docs/sync-protocol.md, розділ 8): у `attempt`,
`module_progress`, `rollcall_status` — `change_seq` (послідовність) і `change_xid` (id транзакції,
xid8 у bigint). Обидва ставить тригер на кожен INSERT і UPDATE, тож жодна зміна не мине стрічку.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "827ed8465b1b"
down_revision: str | Sequence[str] | None = "0edf076a683a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("attempt", "module_progress", "rollcall_status")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE sync_change_seq AS bigint")
    op.execute(
        """
        CREATE FUNCTION sync_change_stamp() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.change_seq := nextval('sync_change_seq');
            NEW.change_xid := pg_current_xact_id()::text::bigint;
            RETURN NEW;
        END
        $$
        """
    )
    for table in TABLES:
        op.add_column(table, sa.Column("change_seq", sa.BigInteger(), nullable=True))
        op.add_column(table, sa.Column("change_xid", sa.BigInteger(), nullable=True))
        op.execute(
            f"CREATE TRIGGER {table}_sync_change BEFORE INSERT OR UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION sync_change_stamp()"
        )
        # Наявні рядки отримують позицію через той самий тригер.
        op.execute(f"UPDATE {table} SET change_seq = NULL")
        op.alter_column(table, "change_seq", nullable=False)
        op.alter_column(table, "change_xid", nullable=False)
        op.create_index(
            f"ix_{table}_sync_changes", table, ["student_id", "change_xid", "change_seq"]
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_sync_changes", table_name=table)
        op.execute(f"DROP TRIGGER {table}_sync_change ON {table}")
        op.drop_column(table, "change_xid")
        op.drop_column(table, "change_seq")
    op.execute("DROP FUNCTION sync_change_stamp()")
    op.execute("DROP SEQUENCE sync_change_seq")
