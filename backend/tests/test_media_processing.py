"""Стиснення відео сервером (`kind=video_source`, ffmpeg у Celery): стани, ідемпотентність,
ліміт результату, блокування публікації, права. ffmpeg у тестах підмінено."""

import subprocess
import uuid
from pathlib import Path

import pytest
from conftest import auth_header
from httpx import AsyncClient
from test_lessons import QUESTION, add_card, add_module, create_lesson
from test_media import MP4, stored_files, upload

from app.core.config import get_settings
from app.models.lessons import MediaAsset
from app.services import video as video_service

pytestmark = pytest.mark.anyio

MOV = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 200
GIF = b"GIF89a" + b"\x00" * 200
COMPRESSED = b"\x00\x00\x00\x18ftypisom" + b"\x01" * 500


@pytest.fixture
def ffmpeg(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, Path]]:
    """Фейковий ffmpeg: пише COMPRESSED у вихідний файл, тривалість 95 с."""
    calls: list[tuple[Path, Path]] = []

    def fake(settings, source: Path, target: Path) -> int:
        calls.append((source, target))
        target.write_bytes(COMPRESSED)
        return 95

    monkeypatch.setattr(video_service, "run_ffmpeg", fake)
    return calls


async def process(db_session, storage, media_id, settings=None) -> str:
    return await video_service.process_video(
        db_session, storage, settings or get_settings(), uuid.UUID(str(media_id))
    )


async def test_video_source_upload_is_processing_and_enqueued(
    client: AsyncClient, world, media_storage, enqueued
) -> None:
    media_id = uuid.uuid4()
    first = await upload(client, world.teacher_a, "video_source", "video/quicktime", MOV, media_id)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["kind"] == "video" and body["processing_status"] == "processing"
    assert body["mime_type"] == "video/quicktime" and body["size_bytes"] == len(MOV)
    assert body["url"].startswith("/media/video_source/") and body["url"].endswith(".mov")
    assert body["processing_error"] is None and body["attribution"] is None
    tasks = [c for c in enqueued if c.name == "media.process_video"]
    assert [(t.args, t.queue) for t in tasks] == [([str(media_id)], "default")]

    # Повтор того самого файла — наявний запис і ще одна (ідемпотентна) постановка задачі.
    again = await upload(client, world.teacher_a, "video_source", "video/quicktime", MOV, media_id)
    assert again.status_code == 200 and again.json() == body
    assert len([c for c in enqueued if c.name == "media.process_video"]) == 2
    other = await upload(client, world.teacher_a, "video_source", "video/mp4", MP4, media_id)
    assert other.status_code == 409
    assert len(stored_files(media_storage)) == 1

    # Звичайне відео не стискається й задачу не ставить; GIF — як оригінал відео.
    plain = await upload(client, world.teacher_a, "video", "video/mp4", MP4)
    assert plain.json()["processing_status"] == "ready"
    gif = await upload(client, world.teacher_a, "video_source", "image/gif", GIF)
    assert gif.status_code == 201 and gif.json()["processing_status"] == "processing"
    assert len([c for c in enqueued if c.name == "media.process_video"]) == 3


async def test_video_source_validation_and_limits(
    client: AsyncClient, app, world, media_storage
) -> None:
    t = world.teacher_a
    assert (await upload(client, t, "video_source", "video/x-msvideo", MOV)).status_code == 415
    fake = await upload(client, t, "video_source", "video/quicktime", b"not a video" * 10)
    assert fake.status_code == 422 and fake.json()["error"]["code"] == "INVALID_MEDIA"
    # Оригінал може бути більшим за ліміт відео (30 МБ), але не за MEDIA_MAX_VIDEO_SOURCE_BYTES.
    settings = get_settings().model_copy(
        update={"media_max_video_bytes": 100, "media_max_video_source_bytes": 1000}
    )
    app.dependency_overrides[get_settings] = lambda: settings
    big_ok = await upload(client, t, "video_source", "video/mp4", MP4)
    assert big_ok.status_code == 201
    assert (await upload(client, t, "video", "video/mp4", MP4)).status_code == 413
    too_big = await upload(client, t, "video_source", "video/mp4", MP4 + b"\x00" * 1000)
    assert too_big.status_code == 413 and too_big.json()["error"]["details"]["limit"] == 1000
    assert len(stored_files(media_storage)) == 1


async def test_upload_roles(client: AsyncClient, world, media_storage) -> None:
    for user in (world.student_a, world.admin, world.parent_a):
        resp = await upload(client, user, "video_source", "video/mp4", MP4)
        assert resp.status_code == 403
    assert stored_files(media_storage) == []


async def test_process_success_replaces_original(
    client: AsyncClient, world, media_storage, db_session, ffmpeg
) -> None:
    created = await upload(client, world.teacher_a, "video_source", "video/quicktime", MOV)
    media_id = created.json()["id"]
    source_key = created.json()["url"].removeprefix("/media/")

    assert await process(db_session, media_storage, media_id) == "ready"
    ((source, _),) = ffmpeg
    assert source == media_storage.local_path(source_key)
    media = await db_session.get(MediaAsset, uuid.UUID(media_id), populate_existing=True)
    assert media.processing_status == "ready" and media.processing_error is None
    assert media.kind == "video" and media.mime_type == "video/mp4"
    assert media.storage_key.startswith("video/") and media.storage_key.endswith(".mp4")
    assert media.size_bytes == len(COMPRESSED) and media.duration_s == 95
    # source_sha256 лишається хешем оригіналу: повтор завантаження оригіналу ідемпотентний.
    assert media.sha256 != media.source_sha256
    files = stored_files(media_storage)
    assert [f.read_bytes() for f in files] == [COMPRESSED]

    h = auth_header(world.teacher_a)
    out = (await client.get(f"/media/{media_id}", headers=h)).json()
    assert out["processing_status"] == "ready" and out["url"].endswith(".mp4")
    again = await upload(
        client, world.teacher_a, "video_source", "video/quicktime", MOV, uuid.UUID(media_id)
    )
    assert again.status_code == 200 and again.json()["processing_status"] == "ready"

    # Повторний запуск задачі нічого не робить.
    assert await process(db_session, media_storage, media_id) == "skipped"
    assert len(ffmpeg) == 1
    assert await process(db_session, media_storage, uuid.uuid4()) == "skipped"


async def test_process_failures(
    client: AsyncClient, world, media_storage, db_session, ffmpeg, monkeypatch
) -> None:
    async def failed(media_id) -> MediaAsset:
        media = await db_session.get(MediaAsset, uuid.UUID(media_id), populate_existing=True)
        assert media.processing_status == "failed"
        return media

    # Результат більший за ліміт відео.
    big = (await upload(client, world.teacher_a, "video_source", "video/mp4", MP4)).json()
    small_limit = get_settings().model_copy(update={"media_max_video_bytes": 10})
    assert await process(db_session, media_storage, big["id"], small_limit) == "failed"
    assert (await failed(big["id"])).processing_error == "too_large"
    assert stored_files(media_storage) == []  # ні оригіналу, ні результату

    # ffmpeg не зміг прочитати файл.
    def broken(settings, source, target):
        raise video_service.VideoProcessingError(video_service.INVALID_VIDEO)

    monkeypatch.setattr(video_service, "run_ffmpeg", broken)
    bad = (await upload(client, world.teacher_a, "video_source", "video/mp4", MP4)).json()
    assert await process(db_session, media_storage, bad["id"]) == "failed"
    assert (await failed(bad["id"])).processing_error == "invalid_video"
    resp = await client.get(f"/media/{bad['id']}", headers=auth_header(world.teacher_a))
    assert resp.json()["processing_status"] == "failed"
    assert resp.json()["processing_error"] == "invalid_video"

    # Оригінал зник зі сховища.
    lost = (await upload(client, world.teacher_a, "video_source", "video/mp4", MP4)).json()
    for f in stored_files(media_storage):
        f.unlink()
    assert await process(db_session, media_storage, lost["id"]) == "failed"
    assert (await failed(lost["id"])).processing_error == "source_missing"
    assert await process(db_session, media_storage, lost["id"]) == "skipped"


def test_run_ffmpeg_arguments_duration_and_errors(monkeypatch, tmp_path) -> None:
    settings = get_settings().model_copy(update={"ffmpeg_path": "/opt/ffmpeg"})
    source, target = tmp_path / "in.mov", tmp_path / "out.mp4"
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"], seen["kwargs"] = args, kwargs
        Path(args[-1]).write_bytes(COMPRESSED)
        stderr = b"Input #0, mov\n  Duration: 00:01:35.40, start: 0.000000, bitrate: 900 kb/s\n"
        return subprocess.CompletedProcess(args, 0, b"", stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert video_service.run_ffmpeg(settings, source, target) == 95
    args = seen["args"]
    assert args[0] == "/opt/ffmpeg" and args[args.index("-i") + 1] == str(source)
    assert args[-1] == str(target)
    assert "libx264" in args and args[args.index("-profile:v") + 1] == "main"
    assert args[args.index("-crf") + 1] == "28" and args[args.index("-maxrate") + 1] == "1200k"
    assert args[args.index("-c:a") + 1] == "aac" and args[args.index("-b:a") + 1] == "96k"
    assert args[args.index("-movflags") + 1] == "+faststart"
    assert args[args.index("-map_metadata") + 1] == "-1"
    assert "0:a:0?" in args  # звук лишається, якщо є
    vf = args[args.index("-vf") + 1]
    assert "1280" in vf and "720" in vf and "force_divisible_by=2" in vf
    assert seen["kwargs"]["timeout"] == settings.media_video_process_timeout_s

    def exit_1(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, b"", b"Invalid data found")

    monkeypatch.setattr(subprocess, "run", exit_1)
    with pytest.raises(video_service.VideoProcessingError) as err:
        video_service.run_ffmpeg(settings, source, tmp_path / "none.mp4")
    assert err.value.reason == "invalid_video"

    def hang(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)
    with pytest.raises(video_service.VideoProcessingError) as err:
        video_service.run_ffmpeg(settings, source, target)
    assert err.value.reason == "timeout"
    assert video_service.parse_duration(b"no duration here") is None


async def test_publish_waits_for_processing(
    client: AsyncClient, world, factory, media_storage, db_session, ffmpeg, monkeypatch
) -> None:
    subject = await factory.subject()
    h = auth_header(world.teacher_a)
    lesson = await create_lesson(client, world.teacher_a, subject)
    lid = lesson["id"]
    module = (await add_module(client, world.teacher_a, lid)).json()
    video = (await upload(client, world.teacher_a, "video_source", "video/mp4", MP4)).json()
    card = await add_card(client, world.teacher_a, module["id"], "video", video["id"])
    assert card.status_code == 201
    assert card.json()["media"]["processing_status"] == "processing"
    # Чуже відео в картку не взяти.
    own = await create_lesson(client, world.teacher_b, subject)
    own_module = (await add_module(client, world.teacher_b, own["id"])).json()
    assert (
        await add_card(client, world.teacher_b, own_module["id"], "video", video["id"])
    ).status_code == 404

    draft = (await client.get(f"/lessons/{lid}", headers=h)).json()
    # Оригінал до 300 МБ не рахується в розмір уроку.
    assert draft["size_bytes"] < len(MP4)
    failed = await client.post(f"/lessons/{lid}/publish", headers=h)
    assert failed.status_code == 422
    (problem,) = failed.json()["error"]["details"]
    assert problem["check"] == "video_processing"
    assert problem["card_id"] == card.json()["id"] and problem["media_asset_id"] == video["id"]
    assert problem["module_id"] == module["id"]

    assert await process(db_session, media_storage, video["id"]) == "ready"
    published = await client.post(f"/lessons/{lid}/publish", headers=h)
    assert published.status_code == 200, published.text
    assert [w["check"] for w in published.json()["warnings"]] == ["video_subtitles"]
    assert published.json()["size_bytes"] >= len(COMPRESSED)

    # Відео, яке не стиснулось, блокує публікацію.
    other = await create_lesson(client, world.teacher_a, subject)
    m2 = (await add_module(client, world.teacher_a, other["id"])).json()
    bad = (await upload(client, world.teacher_a, "video_source", "video/mp4", MP4)).json()
    await add_card(client, world.teacher_a, m2["id"], "video", bad["id"])

    def broken(settings, source, target):
        raise video_service.VideoProcessingError(video_service.INVALID_VIDEO)

    monkeypatch.setattr(video_service, "run_ffmpeg", broken)
    assert await process(db_session, media_storage, bad["id"]) == "failed"
    resp = await client.post(f"/lessons/{other['id']}/publish", headers=h)
    assert [d["check"] for d in resp.json()["error"]["details"]] == ["video_failed"]


async def test_copied_lesson_video_finishes_with_the_original(
    client: AsyncClient, world, factory, media_storage, db_session, ffmpeg
) -> None:
    """Копія уроку колеги посилається на той самий оригінал: стиснення оновлює обидва записи."""
    subject = await factory.subject(world.school)
    lesson = await create_lesson(client, world.teacher_a, subject)
    module = (await add_module(client, world.teacher_a, lesson["id"])).json()
    video = (await upload(client, world.teacher_a, "video_source", "video/mp4", MP4)).json()
    await add_card(client, world.teacher_a, module["id"], "video", video["id"])
    test = await client.post(
        f"/lessons/{lesson['id']}/tests",
        json={"id": str(uuid.uuid4()), "title": "Тест"},
        headers=auth_header(world.teacher_a),
    )
    await client.post(
        f"/tests/{test.json()['id']}/questions",
        json={**QUESTION, "id": str(uuid.uuid4())},
        headers=auth_header(world.teacher_a),
    )
    copy = await client.post(
        f"/lessons/{lesson['id']}/copy",
        json={"id": str(uuid.uuid4())},
        headers=auth_header(world.teacher_b),
    )
    assert copy.status_code == 201, copy.text
    copied = copy.json()["modules"][0]["cards"][0]["media"]
    assert copied["id"] != video["id"] and copied["processing_status"] == "processing"

    assert await process(db_session, media_storage, video["id"]) == "ready"
    hb = auth_header(world.teacher_b)
    after = (await client.get(f"/media/{copied['id']}", headers=hb)).json()
    assert after["processing_status"] == "ready" and after["url"].endswith(".mp4")
    assert await process(db_session, media_storage, copied["id"]) == "skipped"
    assert len(stored_files(media_storage)) == 1
