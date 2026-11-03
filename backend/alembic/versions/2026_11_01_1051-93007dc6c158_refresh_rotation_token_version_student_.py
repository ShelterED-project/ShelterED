"""Refresh rotation, token version, student name key

Revision ID: 93007dc6c158
Revises: a40c36c2b02b
Create Date: 2026-11-01 10:51:10.786090+00:00

"""

import re
import secrets
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "93007dc6c158"
down_revision: str | Sequence[str] | None = "a40c36c2b02b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_APOSTROPHES = re.compile("[’ʼ‘`]")
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _clean(value: str) -> str:
    # Копія app.services.auth.clean_name: міграція не залежить від коду застосунку.
    return " ".join(_APOSTROPHES.sub("'", unicodedata.normalize("NFKC", value)).split())


def _normalize_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("app_user", sa.Column("name_key", sa.Text(), nullable=True))
    op.add_column(
        "app_user",
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("ix_app_user_name_key", "app_user", ["name_key"], unique=False)
    op.add_column(
        "refresh_token", sa.Column("rotated_at", postgresql.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "refresh_token",
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"], unique=False)

    bind = op.get_bind()
    # Раніше ротований токен позначався лише revoked_at; тепер це rotated_at. revoked_at лишаємо:
    # старі токени не отримують пільгового вікна повтору.
    op.execute("UPDATE refresh_token SET rotated_at = revoked_at WHERE replaced_by_id IS NOT NULL")

    students = bind.execute(
        sa.text("SELECT id, display_name, last_name FROM app_user WHERE role = 'student'")
    ).all()
    for user_id, display_name, last_name in students:
        key = f"{_clean(display_name).casefold()}	{_clean(last_name or '').casefold()}"
        bind.execute(
            sa.text("UPDATE app_user SET name_key = :key WHERE id = :id"),
            {"key": key, "id": user_id},
        )

    # Нормалізуємо коди класів до появи CHECK. Порожній результат або колізія => новий код.
    rows = bind.execute(sa.text("SELECT id, join_code FROM school_class")).all()
    taken = {code for _, code in rows if code == _normalize_code(code) and code}
    for class_id, code in rows:
        if code and code == _normalize_code(code):
            continue
        new = _normalize_code(code)
        while not new or new in taken:
            new = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        taken.add(new)
        bind.execute(
            sa.text("UPDATE school_class SET join_code = :code WHERE id = :id"),
            {"code": new, "id": class_id},
        )
    op.create_check_constraint("join_code_format", "school_class", "join_code ~ '^[A-Z0-9]+$'")


def downgrade() -> None:
    """Downgrade schema."""
    # Дані не втрачаються: нові стовпці лише похідні, коди класів лишаються нормалізованими.
    op.drop_constraint("join_code_format", "school_class", type_="check")
    op.drop_index("ix_refresh_token_user_id", table_name="refresh_token")
    op.drop_column("refresh_token", "token_version")
    op.drop_column("refresh_token", "rotated_at")
    op.drop_index("ix_app_user_name_key", table_name="app_user")
    op.drop_column("app_user", "token_version")
    op.drop_column("app_user", "name_key")
