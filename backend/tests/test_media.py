"""Завантаження медіа: формат, сигнатура, ліміти, ідемпотентність, права."""

import uuid

import pytest
from conftest import auth_header
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200
VTT = "WEBVTT\n\n00:00.000 --> 00:02.000\nПривіт, клас!\n".encode()


async def upload(
    client: AsyncClient, user, kind: str, mime: str, content, media_id: uuid.UUID | None = None
):
    return await client.put(
        f"/media/{media_id or uuid.uuid4()}",
        params={"kind": kind},
        content=content,
        headers={**auth_header(user), "Content-Type": mime},
    )


def stored_files(storage) -> list:
    return [p for p in storage.root.rglob("*") if p.is_file()]


async def test_upload_image_idempotent(client: AsyncClient, world, media_storage) -> None:
    media_id = uuid.uuid4()
    first = await upload(client, world.teacher_a, "image", "image/png", PNG, media_id)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["kind"] == "image" and body["size_bytes"] == len(PNG)
    assert body["url"].startswith("/media/image/") and body["url"].endswith(".png")
    files = stored_files(media_storage)
    assert len(files) == 1 and files[0].read_bytes() == PNG
    # Ім'я файла генерує сервер (id + випадковий суфікс), не клієнт.
    assert files[0].name.startswith(str(media_id))
    again = await upload(client, world.teacher_a, "image", "image/png", PNG, media_id)
    assert again.status_code == 200 and again.json() == body
    other = await upload(client, world.teacher_a, "image", "image/jpeg", JPEG, media_id)
    assert other.status_code == 409 and other.json()["error"]["code"] == "ID_CONFLICT"
    stolen = await upload(client, world.teacher_b, "image", "image/png", PNG, media_id)
    assert stolen.status_code == 409
    assert len(stored_files(media_storage)) == 1


async def test_rejects_wrong_type_and_signature(client: AsyncClient, world, media_storage) -> None:
    t = world.teacher_a
    gif = await upload(client, t, "image", "image/gif", b"GIF89a" + b"\x00" * 20)
    assert gif.status_code == 415 and gif.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert (await upload(client, t, "video", "image/png", PNG)).status_code == 415
    fake = await upload(client, t, "image", "image/png", JPEG)
    assert fake.status_code == 422 and fake.json()["error"]["code"] == "INVALID_MEDIA"
    assert (
        await upload(client, t, "subtitles", "text/vtt", b"NOT A VTT FILE\n")
    ).status_code == 422
    bad_utf8 = await upload(client, t, "subtitles", "text/vtt", b"WEBVTT\n\n\xff\xfe broken")
    assert bad_utf8.status_code == 422
    assert (await upload(client, t, "image", "image/png", b"")).status_code == 422
    ok = await upload(client, t, "subtitles", "text/vtt; charset=utf-8", VTT)
    assert ok.status_code == 201
    assert len(stored_files(media_storage)) == 1


async def test_size_limit(client: AsyncClient, world, media_storage) -> None:
    big = PNG + b"\x00" * (2 * 1024 * 1024)
    # Content-Length більший за ліміт — відмова ще до читання тіла.
    resp = await upload(client, world.teacher_a, "image", "image/png", big)
    assert resp.status_code == 413 and resp.json()["error"]["code"] == "MEDIA_TOO_LARGE"

    # Без Content-Length (chunked): ліміт перевіряється на льоту, недописаний файл прибирається.
    async def chunks():
        for start in range(0, len(big), 64 * 1024):
            end = start + 64 * 1024
            yield big[start:end]

    streamed = await upload(client, world.teacher_a, "image", "image/png", chunks())
    assert streamed.status_code == 413
    assert stored_files(media_storage) == []


async def test_only_teacher_uploads(client: AsyncClient, world, media_storage) -> None:
    for user in (world.admin, world.student_a, world.parent_a):
        assert (await upload(client, user, "image", "image/png", PNG)).status_code == 403
    resp = await client.put(
        f"/media/{uuid.uuid4()}",
        params={"kind": "image"},
        content=PNG,
        headers={"Content-Type": "image/png"},
    )
    assert resp.status_code == 401


async def test_attach_subtitles_and_read_access(
    client: AsyncClient, world, factory, media_storage
) -> None:
    video = (await upload(client, world.teacher_a, "video", "video/mp4", MP4)).json()
    vtt = (await upload(client, world.teacher_a, "subtitles", "text/vtt", VTT)).json()
    image = (await upload(client, world.teacher_a, "image", "image/png", PNG)).json()
    foreign_vtt = (await upload(client, world.teacher_b, "subtitles", "text/vtt", VTT)).json()
    headers = auth_header(world.teacher_a)
    url = f"/media/{video['id']}"
    assert (
        await client.patch(url, json={"subtitles_id": image["id"]}, headers=headers)
    ).status_code == 422
    assert (
        await client.patch(url, json={"subtitles_id": foreign_vtt["id"]}, headers=headers)
    ).status_code == 404
    ok = await client.patch(url, json={"subtitles_id": vtt["id"]}, headers=headers)
    assert ok.status_code == 200 and ok.json()["subtitles_id"] == vtt["id"]
    # Чуже відео змінювати не можна.
    assert (
        await client.patch(url, json={"subtitles_id": None}, headers=auth_header(world.teacher_b))
    ).status_code == 403
    # Читання: вчителі й адмін школи — так, інша школа й учень — ні.
    for user in (world.teacher_b, world.admin):
        assert (await client.get(url, headers=auth_header(user))).status_code == 200
    other_teacher = await factory.teacher(world.other_school)
    assert (await client.get(url, headers=auth_header(other_teacher))).status_code == 403
    assert (await client.get(url, headers=auth_header(world.other_admin))).status_code == 403
    assert (await client.get(url, headers=auth_header(world.student_a))).status_code == 403
    assert (await client.get(f"/media/{uuid.uuid4()}", headers=headers)).status_code == 404
