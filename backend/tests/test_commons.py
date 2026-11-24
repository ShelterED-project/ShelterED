"""Імпорт медіа з Wikimedia Commons: ліцензії, підпис, типи, SSRF, ідемпотентність, ліміт.
Мережа підмінена httpx.MockTransport — справжніх запитів немає."""

import io
import json
import uuid
from urllib.parse import quote

import httpx
import pytest
from conftest import auth_header
from httpx import AsyncClient
from PIL import Image
from test_media import stored_files

from app.api.media import get_commons_transport
from app.core.config import get_settings
from app.core.errors import AppError
from app.services import commons

pytestmark = pytest.mark.anyio


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "blue").save(buf, "PNG")
    return buf.getvalue()


PNG = _png()
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 300
GIF = b"GIF89a" + b"\x00" * 300

CC0 = {
    "LicenseShortName": {"value": "CC0"},
    "License": {"value": "cc0"},
    "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Zapotz">Zapotz</a>'},
}
UPLOAD = "https://upload.wikimedia.org/wikipedia/commons"

# Назва файла → (imageinfo, вміст за URL файла).
FILES: dict[str, tuple[dict, bytes]] = {
    "Fraction Circles Shaded.png": (
        {
            "url": f"{UPLOAD}/1/1a/Fraction_Circles_Shaded.png",
            "thumburl": f"{UPLOAD}/thumb/1/1a/Fraction_Circles_Shaded.png/1280px-x.png",
            "mime": "image/png",
            "extmetadata": CC0,
        },
        PNG,
    ),
    "Pottery.jpg": (
        {
            "url": f"{UPLOAD}/2/2b/Pottery.jpg",
            "thumburl": f"{UPLOAD}/thumb/2/2b/Pottery.jpg/1280px-Pottery.jpg",
            "mime": "image/png",
            "extmetadata": {
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                "License": {"value": "cc-by-sa-4.0"},
                "Artist": {"value": "<span>Ismoon &amp; <b>friends</b></span>\n"},
            },
        },
        PNG,
    ),
    "Cake quarters.svg": (
        {
            "url": f"{UPLOAD}/3/3c/Cake_quarters.svg",
            "thumburl": f"{UPLOAD}/thumb/3/3c/Cake_quarters.svg/1280px-Cake_quarters.svg.png",
            "mime": "image/svg+xml",
            "extmetadata": {
                "LicenseShortName": {"value": "Public domain"},
                "License": {"value": "pd"},
            },
        },
        PNG,
    ),
    "Melting ice.webm": (
        {
            "url": f"{UPLOAD}/4/4d/Melting_ice.webm",
            "thumburl": f"{UPLOAD}/thumb/4/4d/Melting_ice.webm/1280px-x.jpg",
            "mime": "video/webm",
            "extmetadata": {
                "LicenseShortName": {"value": "CC BY 2.0"},
                "License": {"value": "cc-by-2.0"},
                "Artist": {"value": "Always Shooting"},
            },
        },
        WEBM,
    ),
    "Proof.gif": (
        {"url": f"{UPLOAD}/5/5e/Proof.gif", "mime": "image/gif", "extmetadata": CC0},
        GIF,
    ),
    "NonCommercial.jpg": (
        {
            "url": f"{UPLOAD}/6/6f/NonCommercial.jpg",
            "mime": "image/jpeg",
            "extmetadata": {
                "LicenseShortName": {"value": "CC BY-NC-SA 4.0"},
                "License": {"value": "cc-by-nc-sa-4.0"},
            },
        },
        PNG,
    ),
    "Song.mp3": (
        {"url": f"{UPLOAD}/7/70/Song.mp3", "mime": "audio/mpeg", "extmetadata": CC0},
        b"ID3",
    ),
    "Evil.png": (
        {"url": "https://evil.example.com/x.png", "mime": "image/png", "extmetadata": CC0},
        PNG,
    ),
    "Redirect.png": (
        {"url": f"{UPLOAD}/8/80/Redirect.png", "mime": "image/png", "extmetadata": CC0},
        PNG,
    ),
}


class FakeCommons:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.fail: Exception | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        if request.url.host == "commons.wikimedia.org" and request.url.path == "/w/api.php":
            title = request.url.params["titles"]
            name = title.removeprefix("File:")
            if name not in FILES:
                return httpx.Response(
                    200, json={"query": {"pages": [{"title": title, "missing": True}]}}
                )
            info, _ = FILES[name]
            body = {"query": {"pages": [{"title": title, "imageinfo": [info]}]}}
            return httpx.Response(200, content=json.dumps(body).encode())
        if request.url.host == "upload.wikimedia.org":
            if "Redirect.png" in request.url.path:
                return httpx.Response(302, headers={"location": "http://169.254.169.254/meta"})
            for info, content in FILES.values():
                if str(request.url) in (info["url"], info.get("thumburl")):
                    mime = (
                        "image/png"
                        if info["mime"].startswith("image/") and "gif" not in info["mime"]
                        else info["mime"]
                    )
                    return httpx.Response(200, content=content, headers={"content-type": mime})
        return httpx.Response(404)


@pytest.fixture
def fake(app) -> FakeCommons:
    commons_fake = FakeCommons()
    transport = httpx.MockTransport(commons_fake.handler)
    app.dependency_overrides[get_commons_transport] = lambda: transport
    return commons_fake


async def import_(client: AsyncClient, user, url: str, media_id: uuid.UUID | None = None):
    return await client.post(
        "/media/import/commons",
        json={"id": str(media_id or uuid.uuid4()), "url": url},
        headers=auth_header(user),
    )


async def test_import_image_with_attribution_and_idempotency(
    client: AsyncClient, world, media_storage, fake
) -> None:
    media_id = uuid.uuid4()
    page = "https://commons.wikimedia.org/wiki/File:Fraction_Circles_Shaded.png"
    resp = await import_(client, world.teacher_a, page, media_id)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "image" and body["processing_status"] == "ready"
    assert body["attribution"] == "Автор: Zapotz · CC0 · Wikimedia Commons"
    assert body["source_url"] == page
    # API запитано з описовим User-Agent без контактів, файл — мініатюра 1280 px.
    api, download = fake.requests
    assert api.headers["user-agent"] == get_settings().commons_user_agent
    assert "@" not in api.headers["user-agent"]
    assert api.url.params["iiurlwidth"] == "1280" and "extmetadata" in api.url.params["iiprop"]
    assert "/thumb/" in download.url.path
    assert len(stored_files(media_storage)) == 1

    # Повтор тим самим файлом в іншому записі (назва, upload-посилання) — 200 без мережі.
    for same in (
        "File:Fraction Circles Shaded.png",
        f"{UPLOAD}/1/1a/Fraction_Circles_Shaded.png",
        f"{UPLOAD}/thumb/1/1a/Fraction_Circles_Shaded.png/640px-Fraction_Circles_Shaded.png",
    ):
        again = await import_(client, world.teacher_a, same, media_id)
        assert again.status_code == 200 and again.json() == body
    assert len(fake.requests) == 2
    other = await import_(client, world.teacher_a, "File:Pottery.jpg", media_id)
    assert other.status_code == 409 and other.json()["error"]["code"] == "ID_CONFLICT"
    stolen = await import_(client, world.teacher_b, page, media_id)
    assert stolen.status_code == 409

    # Атрибуція йде в картку редактора.
    h = auth_header(world.teacher_a)
    assert (await client.get(f"/media/{media_id}", headers=h)).json()["attribution"]


async def test_attribution_strips_html_and_svg_uses_png(
    client: AsyncClient, world, media_storage, fake
) -> None:
    sa = await import_(client, world.teacher_a, "File:Pottery.jpg")
    assert sa.json()["attribution"] == "Автор: Ismoon & friends · CC BY-SA 4.0 · Wikimedia Commons"
    svg = await import_(
        client, world.teacher_a, "https://commons.wikimedia.org/wiki/File:Cake_quarters.svg"
    )
    assert svg.status_code == 201, svg.text
    assert svg.json()["kind"] == "image" and svg.json()["mime_type"] in ("image/png", "image/webp")
    assert svg.json()["attribution"] == "Public domain · Wikimedia Commons"
    assert fake.requests[-1].url.path.endswith(".svg.png")


async def test_import_video_and_gif_go_to_server_compression(
    client: AsyncClient, world, media_storage, fake, enqueued
) -> None:
    video = await import_(client, world.teacher_a, "File:Melting_ice.webm")
    assert video.status_code == 201, video.text
    body = video.json()
    assert body["kind"] == "video" and body["processing_status"] == "processing"
    assert body["mime_type"] == "video/webm" and body["url"].startswith("/media/video_source/")
    assert body["attribution"] == "Автор: Always Shooting · CC BY 2.0 · Wikimedia Commons"
    gif = await import_(client, world.teacher_a, "File:Proof.gif")
    assert gif.json()["processing_status"] == "processing"
    tasks = [c.args for c in enqueued if c.name == "media.process_video"]
    assert tasks == [[body["id"]], [gif.json()["id"]]]


async def test_rejected_files(client: AsyncClient, world, media_storage, fake) -> None:
    t = world.teacher_a
    nc = await import_(client, t, "File:NonCommercial.jpg")
    assert nc.status_code == 422 and nc.json()["error"]["code"] == "LICENSE_NOT_ALLOWED"
    assert nc.json()["error"]["details"]["license"] == "CC BY-NC-SA 4.0"
    audio = await import_(client, t, "File:Song.mp3")
    assert audio.status_code == 415
    missing = await import_(client, t, "File:Nope.png")
    assert (
        missing.status_code == 404 and missing.json()["error"]["code"] == "COMMONS_FILE_NOT_FOUND"
    )
    # SSRF: посилання з API поза wikimedia.org і редирект на внутрішню адресу не запитуються.
    before = len(fake.requests)
    evil = await import_(client, t, "File:Evil.png")
    assert evil.status_code == 502 and evil.json()["error"]["code"] == "COMMONS_UNAVAILABLE"
    assert len(fake.requests) == before + 1  # лише API
    redirect = await import_(client, t, "File:Redirect.png")
    assert redirect.status_code == 502
    assert not any(r.url.host == "169.254.169.254" for r in fake.requests)
    for bad in (
        "https://evil.example.com/wiki/File:X.png",
        "http://commons.wikimedia.org/wiki/File:X.png",
        "https://commons.wikimedia.org/wiki/Main_Page",
        "Just a title",
        "https://upload.wikimedia.org/etc/passwd",
    ):
        resp = await import_(client, t, bad)
        assert resp.status_code == 422, bad
        assert resp.json()["error"]["code"] == "INVALID_COMMONS_URL"
    assert stored_files(media_storage) == []

    fake.fail = httpx.ConnectTimeout("timeout")
    down = await import_(client, t, "File:Pottery.jpg")
    assert down.status_code == 502 and down.json()["error"]["code"] == "COMMONS_UNAVAILABLE"


async def test_roles_and_rate_limit(client: AsyncClient, app, world, media_storage, fake) -> None:
    for user in (world.student_a, world.admin, world.parent_a):
        assert (await import_(client, user, "File:Pottery.jpg")).status_code == 403
    settings = get_settings().model_copy(update={"rate_limit_commons_import": 2})
    app.dependency_overrides[get_settings] = lambda: settings
    for _ in range(2):
        assert (await import_(client, world.teacher_a, "File:Pottery.jpg")).status_code == 201
    limited = await import_(client, world.teacher_a, "File:Pottery.jpg")
    assert limited.status_code == 429 and limited.headers["Retry-After"]
    # Ліміт — на вчителя.
    assert (await import_(client, world.teacher_b, "File:Pottery.jpg")).status_code == 201


def test_parse_title_and_license_rules() -> None:
    assert commons.parse_title("file:melting_ice.webm") == "File:Melting ice.webm"
    assert (
        commons.parse_title(
            "https://commons.wikimedia.org/wiki/File:" + quote("Десятинна_церква.jpg")
        )
        == "File:Десятинна церква.jpg"
    )
    assert (
        commons.parse_title("https://commons.wikimedia.org/w/index.php?title=File:A_b.jpg")
        == "File:A b.jpg"
    )
    assert commons.source_url("File:A b (1).jpg") == (
        "https://commons.wikimedia.org/wiki/File:A_b_(1).jpg"
    )
    for name in ("cc0", "pd", "CC BY 4.0", "CC BY-SA 3.0", "cc-by-sa-4.0", "Public domain"):
        assert commons.license_name({"extmetadata": {"License": {"value": name}}})
    for name in ("cc-by-nc-4.0", "CC BY-ND 2.0", "GFDL", "Fair use", ""):
        with pytest.raises(AppError):
            commons.license_name({"extmetadata": {"LicenseShortName": {"value": name}}})
    for url in (
        "http://upload.wikimedia.org/x",
        "https://upload.wikimedia.org.evil.com/x",
        "https://user@upload.wikimedia.org/x",
        "https://upload.wikimedia.org:8080/x",
        "https://localhost/x",
    ):
        with pytest.raises(AppError):
            commons.check_fetch_url(url)
    assert commons.check_fetch_url("https://upload.wikimedia.org/a.png").host


def test_author_footnote_falls_back_to_credit() -> None:
    info = {
        "extmetadata": {
            "Artist": {"value": '<a href="https://www.flickr.com/people/x">[1]</a>'},
            "Credit": {"value": '<a href="https://www.flickr.com/photos/x/1">Always Shooting</a>'},
        }
    }
    assert commons.attribution(info, "CC BY 2.0") == (
        "Автор: Always Shooting · CC BY 2.0 · Wikimedia Commons"
    )
