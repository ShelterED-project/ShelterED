"""test analysis

`test_analysis`: AI-аналіз тесту класу (кнопка вчителя «Проаналізувати»): статус, відповідь AI
зі справжніми id учнів (`result`, без імен), код помилки. Не більше одного `processing` на тест
класу (частковий унікальний індекс). `test_analysis_edit`: правки вчителя у фідбеку учню й
батькам. Учні — ON DELETE CASCADE для правок; з `result` учня прибирає сервіс видалення (B15).

Revision ID: 8b72a9500e68
Revises: d4a7c1e9b562
Create Date: 2026-11-26 13:11:28.130673+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8b72a9500e68"
down_revision: str | Sequence[str] | None = "d4a7c1e9b562"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "test_analysis",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("test_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts_count", sa.Integer(), nullable=False),
        sa.Column(
            "result", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'draft', 'published', 'failed')",
            name=op.f("ck_test_analysis_status"),
        ),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["school_class.id"],
            name=op.f("fk_test_analysis_class_id_school_class"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["app_user.id"],
            name=op.f("fk_test_analysis_created_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["test_id"], ["test.id"], name=op.f("fk_test_analysis_test_id_test"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_analysis")),
    )
    op.create_index(
        "ix_test_analysis_class_id_test_id",
        "test_analysis",
        ["class_id", "test_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_test_analysis_result", "test_analysis", ["result"], unique=False, postgresql_using="gin"
    )
    op.create_index(
        "uq_test_analysis_processing",
        "test_analysis",
        ["class_id", "test_id"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.create_table(
        "test_analysis_edit",
        sa.Column("analysis_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("student_text", sa.Text(), nullable=True),
        sa.Column("parent_text", sa.Text(), nullable=True),
        sa.Column("edited_by", sa.UUID(), nullable=True),
        sa.Column(
            "edited_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["test_analysis.id"],
            name=op.f("fk_test_analysis_edit_analysis_id_test_analysis"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["edited_by"],
            ["app_user.id"],
            name=op.f("fk_test_analysis_edit_edited_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["app_user.id"],
            name=op.f("fk_test_analysis_edit_student_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("analysis_id", "student_id", name=op.f("pk_test_analysis_edit")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("test_analysis_edit")
    op.drop_index(
        "uq_test_analysis_processing",
        table_name="test_analysis",
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.drop_index("ix_test_analysis_result", table_name="test_analysis", postgresql_using="gin")
    op.drop_index("ix_test_analysis_class_id_test_id", table_name="test_analysis")
    op.drop_table("test_analysis")
