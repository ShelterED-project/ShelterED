"""question kinds text/match, explanation, lesson copy source

- `question.kind`: нові типи `text` (коротка відповідь) і `match` (відповідність);
  `question.right_options` — праві елементи `match` (NULL для інших типів, CHECK);
- `question.explanation` — пояснення для розбору помилок після тренувального тесту;
- `lesson.copied_from_id` — урок-джерело копії (ідемпотентний повтор копіювання).

Нових даних про дітей немає.

Downgrade: питання `text` і `match` старою схемою не описати, тож вони видаляються (разом з
агрегатами `class_question_stat` каскадом); пояснення й джерело копії губляться.

Revision ID: 5d1e7c2a9b40
Revises: 430365394792
Create Date: 2026-11-24 12:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5d1e7c2a9b40"
down_revision: str | Sequence[str] | None = "430365394792"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "question",
        sa.Column("right_options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("question", sa.Column("explanation", sa.Text(), nullable=True))
    op.drop_constraint(op.f("ck_question_kind"), "question", type_="check")
    op.create_check_constraint(
        "kind", "question", "kind IN ('single', 'multiple', 'text', 'match')"
    )
    op.create_check_constraint(
        "right_options", "question", "(kind = 'match') = (right_options IS NOT NULL)"
    )

    op.add_column("lesson", sa.Column("copied_from_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_lesson_copied_from_id_lesson"),
        "lesson",
        "lesson",
        ["copied_from_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_lesson_copied_from_id", "lesson", ["copied_from_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_lesson_copied_from_id", table_name="lesson")
    op.drop_constraint(op.f("fk_lesson_copied_from_id_lesson"), "lesson", type_="foreignkey")
    op.drop_column("lesson", "copied_from_id")

    op.execute("DELETE FROM question WHERE kind NOT IN ('single', 'multiple')")
    op.drop_constraint(op.f("ck_question_right_options"), "question", type_="check")
    op.drop_constraint(op.f("ck_question_kind"), "question", type_="check")
    op.create_check_constraint("kind", "question", "kind IN ('single', 'multiple')")
    op.drop_column("question", "explanation")
    op.drop_column("question", "right_options")
