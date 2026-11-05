"""Ідемпотентне створення рядків з клієнтським id (принципи 2–3 offline-first)."""

from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError


def id_conflict(fields: list[str]) -> AppError:
    return AppError(
        "ID_CONFLICT",
        "Resource with this id already exists with different data",
        status_code=409,
        details={"fields": fields},
    )


async def insert_or_get[T](
    session: AsyncSession,
    model: type[T],
    values: Mapping[str, Any],
    *,
    constraint_errors: Mapping[str, AppError] | None = None,
    compare: Iterable[str] | None = None,
) -> tuple[T, bool]:
    """INSERT ... ON CONFLICT (id) DO NOTHING.

    Новий рядок → (рядок, True). Повтор із тими самими даними → (наявний рядок, False).
    Той самий id з іншими даними (або чужим власником) → 409 ID_CONFLICT.
    Порушення інших унікальних обмежень → помилка з `constraint_errors` за іменем обмеження.
    Commit робить викликач.
    """
    stmt = (
        pg_insert(model)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(model.id)  # type: ignore[attr-defined]
    )
    async with integrity_errors(session, constraint_errors or {}):
        inserted = await session.scalar(stmt)
    obj = await session.get(model, values["id"], populate_existing=True)
    if inserted is not None:
        return obj, True
    keys = list(compare) if compare is not None else [k for k in values if k != "id"]
    diff = [k for k in keys if getattr(obj, k) != values[k]]
    if diff:
        raise id_conflict(diff)
    return obj, False


@asynccontextmanager
async def integrity_errors(
    session: AsyncSession, constraint_errors: Mapping[str, AppError]
) -> AsyncIterator[None]:
    """Зміни всередині блоку пишуться в окремому savepoint. Порушення відомого обмеження
    (за іменем) → відповідна AppError; відкочується лише savepoint, сесія лишається робочою."""
    await session.flush()  # чуже незбережене — поза savepoint, щоб не загубити при відкаті
    try:
        async with session.begin_nested():
            yield
    except IntegrityError as exc:
        for name, error in constraint_errors.items():
            if name in str(exc.orig):
                raise error from exc
        raise
