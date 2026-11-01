"""auth tables and student pin

Revision ID: f2bb4cfc37c4
Revises: a557c94df097
Create Date: 2026-11-01 10:08:17.427417+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2bb4cfc37c4"
down_revision: str | Sequence[str] | None = "a557c94df097"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_code",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("code_challenge", sa.Text(), nullable=False),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=True),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_auth_code_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_code")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_auth_code_code_hash")),
    )
    op.create_table(
        "parent_link_code",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("child_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("used_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["child_id"],
            ["app_user.id"],
            name=op.f("fk_parent_link_code_child_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            name=op.f("fk_parent_link_code_created_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["used_by"],
            ["app_user.id"],
            name=op.f("fk_parent_link_code_used_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parent_link_code")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_parent_link_code_code_hash")),
    )
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_token.id"],
            name=op.f("fk_refresh_token_replaced_by_id_refresh_token"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_refresh_token_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_token_token_hash")),
    )
    op.create_index("ix_refresh_token_family_id", "refresh_token", ["family_id"], unique=False)
    op.add_column("app_user", sa.Column("pin_hash", sa.Text(), nullable=True))
    # Alembic не бачить CHECK при autogenerate, тому додано вручну.
    op.create_check_constraint(
        "pin_only_student", "app_user", "role = 'student' OR pin_hash IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("pin_only_student", "app_user", type_="check")
    op.drop_column("app_user", "pin_hash")
    op.drop_index("ix_refresh_token_family_id", table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_table("parent_link_code")
    op.drop_table("auth_code")
