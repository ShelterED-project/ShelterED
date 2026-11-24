"""media processing status and attribution

- `media_asset.processing_status` (`processing` / `ready` / `failed`, CHECK, за замовчуванням
  `ready`) і `processing_error`: відео, яке стискає сервер (Celery + ffmpeg);
- `media_asset.attribution`, `source_url`: автор і ліцензія файла з Wikimedia Commons.

Нових даних про дітей немає.

Downgrade: відео, які ще стискаються або не стиснулись, старою схемою не описати (їхній
`storage_key` — оригінал до 300 МБ), тож рядки з `processing_status <> 'ready'` видаляються
разом із картками, що на них посилаються; файли в сховищі лишаються. Підписи губляться.

Revision ID: 7c3e9a1f4d21
Revises: 5d1e7c2a9b40
Create Date: 2026-11-24 15:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3e9a1f4d21"
down_revision: str | Sequence[str] | None = "5d1e7c2a9b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "media_asset",
        sa.Column("processing_status", sa.Text(), server_default="ready", nullable=False),
    )
    op.add_column("media_asset", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column("media_asset", sa.Column("attribution", sa.Text(), nullable=True))
    op.add_column("media_asset", sa.Column("source_url", sa.Text(), nullable=True))
    op.create_check_constraint(
        "processing_status",
        "media_asset",
        "processing_status IN ('processing', 'ready', 'failed')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    not_ready = "SELECT id FROM media_asset WHERE processing_status <> 'ready'"
    op.execute(f"DELETE FROM card WHERE media_asset_id IN ({not_ready})")
    op.execute(f"DELETE FROM knowledge_pack_media WHERE media_asset_id IN ({not_ready})")
    op.execute("DELETE FROM media_asset WHERE processing_status <> 'ready'")
    op.drop_constraint(op.f("ck_media_asset_processing_status"), "media_asset", type_="check")
    op.drop_column("media_asset", "source_url")
    op.drop_column("media_asset", "attribution")
    op.drop_column("media_asset", "processing_error")
    op.drop_column("media_asset", "processing_status")
