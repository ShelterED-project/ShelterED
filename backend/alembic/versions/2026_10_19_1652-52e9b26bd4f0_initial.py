"""initial

Revision ID: 52e9b26bd4f0
Revises:
Create Date: 2026-10-19 16:52:39.382908+00:00

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "52e9b26bd4f0"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
