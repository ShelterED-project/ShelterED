"""Пакети знань «Рюкзак»: маніфест і завантаження (заглушки B4, логіка — B6)."""

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.api.deps import AccessibleClass, require_roles
from app.api.stub import R501, example_of, not_implemented
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.packs import PackManifestOut, PackOut

router = APIRouter(tags=["packs"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}

PackReader = Annotated[User, Depends(require_roles("student", "teacher", "admin"))]


@router.get(
    "/packs/manifest",
    response_model=PackManifestOut,
    responses={200: example_of(PackManifestOut), **ACCESS, **R501},
)
async def pack_manifest(
    klass: AccessibleClass,
    date_from: Annotated[
        dt.date | None, Query(alias="from", description="Перший день; за замовчуванням сьогодні")
    ] = None,
    date_to: Annotated[
        dt.date | None, Query(alias="to", description="Останній день; за замовчуванням +6 днів")
    ] = None,
) -> PackManifestOut:
    """Актуальні пакети класу на дні `from`..`to` (до 7 днів): версії, хеші, розміри.
    Медіа — окремим списком з горизонтом «сьогодні + завтра». Учень — свого класу,
    вчитель — своїх класів, адмін — класів школи. `class_id` — query-параметр."""
    raise not_implemented()


@router.get(
    "/packs/{pack_id}",
    response_model=PackOut,
    responses={
        200: {
            **example_of(PackOut),
            "headers": {
                "ETag": {"description": "content_hash пакета", "schema": {"type": "string"}}
            },
        },
        304: {"description": "Не змінився (`If-None-Match` збігся з ETag)"},
        **ACCESS,
        **R501,
    },
)
async def get_pack(
    pack_id: uuid.UUID,
    user: PackReader,
    if_none_match: Annotated[str | None, Header()] = None,
) -> PackOut:
    """Вміст пакета з `ETag`, стиснутий gzip/brotli. Медіа — за URL з маніфесту.
    Доступ — як до класу пакета."""
    raise not_implemented()
