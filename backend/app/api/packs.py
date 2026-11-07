"""Пакети знань «Рюкзак»: маніфест і завантаження (B6)."""

import datetime as dt
import gzip
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api.deps import AccessibleClass, Session, Storage, require_roles
from app.api.stub import example_of
from app.core.errors import AppError
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.packs import PackManifestOut, PackOut
from app.services import auth as auth_service
from app.services import packs as service

router = APIRouter(tags=["packs"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}

PackReader = Annotated[User, Depends(require_roles("student", "teacher", "admin"))]

# Пакет незмінний за id, але клієнт однаково перевіряє його через ETag (дешевий 304).
CACHE_HEADERS = {"Cache-Control": "private, no-cache", "Vary": "Accept-Encoding"}


@router.get(
    "/packs/manifest",
    response_model=PackManifestOut,
    responses={
        200: example_of(PackManifestOut),
        **ACCESS,
        422: {"model": ErrorResponse, "description": "Діапазон: `to` < `from` або > 7 днів"},
    },
)
async def pack_manifest(
    klass: AccessibleClass,
    session: Session,
    storage: Storage,
    date_from: Annotated[
        dt.date | None, Query(alias="from", description="Перший день; за замовчуванням сьогодні")
    ] = None,
    date_to: Annotated[
        dt.date | None, Query(alias="to", description="Останній день; за замовчуванням +6 днів")
    ] = None,
) -> PackManifestOut:
    """Актуальні (найновіші) версії пакетів класу на дні `from`..`to` (до 7 днів): версії,
    хеші, розміри. Дні без уроків у розкладі пакета не мають. Медіа — окремим списком з
    горизонтом «сьогодні + завтра» (за часом школи) у межах діапазону. Учень — свого класу,
    вчитель — своїх класів, адмін — класів школи; батьки — ні. `class_id` — query-параметр."""
    return await service.manifest(session, klass, date_from, date_to, storage)


def _etag_matches(if_none_match: str, etag: str) -> bool:
    for tag in if_none_match.split(","):
        tag = tag.strip()
        if tag == "*" or tag.removeprefix("W/") == etag:
            return True
    return False


def _choose_encoding(accept_encoding: str | None, has_br: bool) -> str | None:
    """Стиснення за `Accept-Encoding` (RFC 9110, з q-значеннями): `br`, якщо клієнт його явно
    приймає (q > 0, не нижче за gzip) і для пакета є brotli-версія; інакше `gzip` — явний
    `gzip`/`x-gzip` з q > 0 або `*` з q > 0 (`gzip;q=0` — відмова); інакше без стиснення."""
    if not accept_encoding:
        return None
    weights: dict[str, float] = {}
    for part in accept_encoding.split(","):
        coding, *params = (p.strip() for p in part.split(";"))
        coding = coding.lower()
        if not coding:
            continue
        q = 1.0
        for param in params:
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    q = float(value.strip())
                except ValueError:
                    q = 0.0
        weights[coding] = q
    gzip_q = 0.0
    for coding in ("gzip", "x-gzip", "*"):
        if coding in weights:
            gzip_q = weights[coding]
            break
    br_q = weights.get("br", 0.0)
    if has_br and br_q > 0 and br_q >= gzip_q:
        return "br"
    return "gzip" if gzip_q > 0 else None


@router.get(
    "/packs/{pack_id}",
    response_model=PackOut,
    responses={
        200: {
            **example_of(PackOut),
            "headers": {
                "ETag": {
                    "description": "`content_hash` пакета в лапках",
                    "schema": {"type": "string"},
                },
                "Content-Encoding": {
                    "description": ("`br` або `gzip` за `Accept-Encoding`, brotli в пріоритеті"),
                    "schema": {"type": "string"},
                },
            },
        },
        304: {"description": "Не змінився (`If-None-Match` збігся з ETag)"},
        **ACCESS,
    },
)
async def get_pack(
    pack_id: uuid.UUID,
    user: PackReader,
    session: Session,
    if_none_match: Annotated[str | None, Header()] = None,
    accept_encoding: Annotated[str | None, Header()] = None,
) -> Response:
    """Вміст версії пакета з `ETag` (= `content_hash` у лапках), стиснутий brotli або gzip
    (за `Accept-Encoding`; brotli в пріоритеті, пакети до його появи — лише gzip).
    Версія незмінна: стара версія лишається доступною за
    своїм id. Медіа — за URL з маніфесту. Доступ — як до класу пакета."""
    pack = await service.get_pack(session, pack_id)
    klass = await auth_service.get_class(session, pack.class_id)
    if klass is None or not await auth_service.can_access_class(session, user, klass):
        raise AppError("FORBIDDEN", "No access to this class", status_code=403)
    etag = f'"{pack.content_hash}"'
    headers = {"ETag": etag, **CACHE_HEADERS}
    if if_none_match and _etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    encoding = _choose_encoding(accept_encoding, pack.content_br is not None)
    if encoding is not None:
        return Response(
            content=pack.content_br if encoding == "br" else pack.content_gzip,
            media_type="application/json",
            headers={**headers, "Content-Encoding": encoding},
        )
    return Response(
        content=gzip.decompress(pack.content_gzip), media_type="application/json", headers=headers
    )
