"""tutor conversation and cached explanations

- `tutor_conversation`: стан розмови учня з ШІ-репетитором (id від клієнта, завдання AI з
  відповіддю, кількість підказок, до 8 останніх реплік, відповіді на останні запити для
  ідемпотентності, ключі вже отриманих закешованих пояснень). Дані дитини: репліки учня;
  видаляються з учнем (ON DELETE CASCADE) і через `RETENTION_TUTOR_CONVERSATION_DAYS` без
  активності.
- `tutor_explanation`: закешовані пояснення, адресовані вмістом (`cache_key` — sha256
  клас + предмет + назва модуля + тексти карток + версія промпту), без прив'язки до уроку:
  спільні для повторних публікацій, копій і онлайн-запитів учнів. Персональних даних немає.

Downgrade видаляє обидві таблиці з даними (розмови й пояснення губляться; пакети,
зібрані з поясненнями, лишаються як є). Лише `drop_table`: спрацьовує й на ранній
(до 25.11.2026, не в проді) формі цих таблиць.

Revision ID: b8e4f2a6c913
Revises: 7c3e9a1f4d21
Create Date: 2026-11-24 18:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8e4f2a6c913"
down_revision: str | Sequence[str] | None = "7c3e9a1f4d21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tutor_conversation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=True),
        sa.Column("module_id", sa.UUID(), nullable=True),
        sa.Column("task", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("hints_used", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "history",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "replies",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "explained_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lesson.id"],
            name=op.f("fk_tutor_conversation_lesson_id_lesson"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["module.id"],
            name=op.f("fk_tutor_conversation_module_id_module"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["app_user.id"],
            name=op.f("fk_tutor_conversation_student_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tutor_conversation")),
    )
    op.create_index(
        "ix_tutor_conversation_student_id", "tutor_conversation", ["student_id"], unique=False
    )
    op.create_index(
        "ix_tutor_conversation_updated_at", "tutor_conversation", ["updated_at"], unique=False
    )
    op.create_table(
        "tutor_explanation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tutor_explanation")),
        sa.UniqueConstraint("cache_key", name=op.f("uq_tutor_explanation_cache_key")),
    )
    op.create_index(
        "ix_tutor_explanation_last_used_at", "tutor_explanation", ["last_used_at"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tutor_explanation")
    op.drop_table("tutor_conversation")
