"""Демо-дані (`python -m app.cli seed`): ідемпотентність, перевірки публікації, охорона prod."""

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app import cli
from app.core.config import get_settings
from app.core.security import verify_secret
from app.core.storage import LocalMediaStorage
from app.models.alerts import AlertEvent
from app.models.lessons import Card, Lesson, MediaAsset, Module, Question, Subject, Test
from app.models.packs import KnowledgePack
from app.models.push import PushSubscription
from app.models.rollcall import RollCallSession, RollCallStatus
from app.models.school import (
    ClassMembership,
    LessonAssignment,
    ParentChild,
    ScheduleSlot,
    School,
    SchoolClass,
    User,
)
from app.models.sync import SyncEvent
from app.seed import content
from app.seed.runner import SeedRefused, seed, sid
from app.services.lessons import publish_problems

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def seed_storage(tmp_path, monkeypatch) -> LocalMediaStorage:
    """Медіа сіду пишуться в тимчасовий каталог тесту, а не в MEDIA_ROOT."""
    from app.seed import runner

    storage = LocalMediaStorage(tmp_path / "seed-media", "/media")
    original = runner.seed

    async def seed_with_storage(*args, **kwargs):
        kwargs.setdefault("storage", storage)
        return await original(*args, **kwargs)

    monkeypatch.setitem(globals(), "seed", seed_with_storage)
    return storage


MODELS = [
    School,
    SchoolClass,
    User,
    ClassMembership,
    ParentChild,
    Subject,
    ScheduleSlot,
    Lesson,
    Module,
    Card,
    Test,
    Question,
    MediaAsset,
    LessonAssignment,
    AlertEvent,
    RollCallSession,
    RollCallStatus,
    SyncEvent,
    KnowledgePack,
]


async def counts(session) -> dict[str, int]:
    return {
        m.__tablename__: await session.scalar(select(func.count()).select_from(m)) for m in MODELS
    }


async def test_seed_twice_changes_nothing(db_session) -> None:
    settings = get_settings()
    first = await seed(db_session, settings)
    assert first.generated_password and first.passwords_set
    assert first.packs_built > 0
    after_first = await counts(db_session)
    admin = await db_session.get(User, sid("user", "admin"))
    hash_before = admin.password_hash

    second = await seed(db_session, settings)
    assert second.generated_password is None and not second.passwords_set
    assert second.packs_built == 0
    assert await counts(db_session) == after_first
    await db_session.refresh(admin)
    assert admin.password_hash == hash_before
    assert verify_secret(first.generated_password, admin.password_hash)

    # SEED_PASSWORD замінює пароль дорослих і відкликає їхні токени.
    db_session.add(
        PushSubscription(
            user_id=admin.id,
            endpoint="https://fcm.googleapis.com/fcm/send/seed-admin",
            p256dh="x",
            auth="y",
        )
    )
    await db_session.flush()
    third = await seed(db_session, settings, password="demo-password-42")
    assert third.passwords_set and third.generated_password is None
    assert await counts(db_session) == after_first
    await db_session.refresh(admin)
    assert verify_secret("demo-password-42", admin.password_hash)
    assert admin.token_version == 1
    subs = select(func.count()).select_from(PushSubscription)
    assert await db_session.scalar(subs.where(PushSubscription.user_id == admin.id)) == 0


async def test_seeded_content_shape_and_publish_checks(db_session) -> None:
    settings = get_settings()
    result = await seed(db_session, settings, password="demo-password-42")
    assert result.problems == {}

    lessons = (
        await db_session.scalars(
            select(Lesson).where(
                Lesson.author_id.in_([sid("user", "teacher5a"), sid("user", "teacher7b")])
            )
        )
    ).all()
    assert len(lessons) >= 12
    per_grade = {5: 0, 7: 0}
    windowed = 0
    for lesson in lessons:
        assert lesson.status == "published" and lesson.shelter_part and lesson.main_part
        assert await publish_problems(db_session, lesson, settings) == []
        per_grade[lesson.grade] += 1
        modules = (
            await db_session.scalars(select(Module).where(Module.lesson_id == lesson.id))
        ).all()
        assert 2 <= len(modules) <= 4
        assert all(3 <= m.duration_min <= 5 for m in modules)
        test = await db_session.scalar(select(Test).where(Test.lesson_id == lesson.id))
        n = await db_session.scalar(
            select(func.count()).select_from(Question).where(Question.test_id == test.id)
        )
        assert 6 <= n <= 8
        windowed += test.window_enabled
    assert per_grade[5] >= 6 and per_grade[7] >= 6
    assert windowed >= 2

    for klass in content.CLASSES:
        members = await db_session.scalar(
            select(func.count())
            .select_from(ClassMembership)
            .where(
                ClassMembership.class_id == sid("class", klass["key"]),
                ClassMembership.member_role == "student",
            )
        )
        assert members == 12
    rollcall = await db_session.get(RollCallSession, sid("drill", "rollcall"))
    assert rollcall.closed_at is not None and rollcall.is_drill


async def test_seeded_student_joins_with_demo_pin(client, db_session) -> None:
    await seed(db_session, get_settings(), password="demo-password-42")
    name, last = content.CLASSES[0]["students"][0]
    response = await client.post(
        "/auth/student/join",
        json={
            "join_code": content.CLASSES[0]["join_code"],
            "display_name": name,
            "last_name": last,
            "pin": content.STUDENT_PIN,
        },
    )
    assert response.status_code == 200, response.text
    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.json()["id"] == str(sid("student", "5a", 0))


async def test_seed_refuses_production(db_session) -> None:
    settings = get_settings().model_copy(update={"environment": "prod"})
    with pytest.raises(SeedRefused):
        await seed(db_session, settings)
    assert await db_session.get(School, sid("school")) is None


def test_cli_seed_refuses_production(monkeypatch, capsys) -> None:
    settings = get_settings().model_copy(update={"environment": "prod"})
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    assert cli.main(["seed"]) == 1
    assert "not allowed" in capsys.readouterr().err


def test_cli_seed_allow_prod_requires_seed_password(monkeypatch, capsys) -> None:
    settings = get_settings().model_copy(update={"environment": "prod", "seed_password": None})
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    assert cli.main(["seed", "--allow-prod"]) == 1
    assert "SEED_PASSWORD is required" in capsys.readouterr().err


def test_seed_password_is_read_from_env_file(tmp_path, monkeypatch, capsys) -> None:
    """SEED_PASSWORD береться через Settings, тож працює і з `.env`, і в repr не видно."""
    from types import SimpleNamespace

    from app.core.config import Settings
    from app.seed import runner

    monkeypatch.delenv("SEED_PASSWORD", raising=False)
    env = tmp_path / ".env"
    env.write_text("SEED_PASSWORD=from-dot-env-42\n", encoding="utf-8")
    settings = Settings(_env_file=env)
    assert settings.seed_password.get_secret_value() == "from-dot-env-42"
    assert "from-dot-env-42" not in repr(settings)

    captured = {}

    async def fake_seed(session, settings, password=None, allow_prod=False):
        captured["password"] = password
        return SimpleNamespace(
            school_id="s",
            join_codes={},
            adult_emails=[],
            generated_password=None,
            passwords_set=True,
            lessons=0,
            packs_built=0,
            problems=[],
        )

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(runner, "seed", fake_seed)
    assert cli.main(["seed"]) == 0
    assert captured["password"] == "from-dot-env-42"
    assert "from-dot-env-42" not in capsys.readouterr().out

    short = settings.model_copy(update={"seed_password": SecretStr("short")})
    monkeypatch.setattr(cli, "get_settings", lambda: short)
    assert cli.main(["seed"]) == 1
    assert "at least 8" in capsys.readouterr().err


async def test_lesson_for_a_date_does_not_depend_on_seed_week(db_session) -> None:
    """Seed «станом на» два різні тижні дає той самий урок на дату з їхнього перетину."""
    import datetime as dt

    settings = get_settings()
    first_monday = dt.date(2026, 11, 2)
    overlap = [first_monday + dt.timedelta(days=d) for d in range(7, 14)]

    async def assigned() -> dict:
        rows = await db_session.execute(
            select(
                LessonAssignment.slot_id, LessonAssignment.date, LessonAssignment.lesson_id
            ).where(LessonAssignment.date.in_(overlap))
        )
        return {(slot, day): lesson for slot, day, lesson in rows}

    await seed(db_session, settings, today=first_monday)
    before = await assigned()
    await seed(db_session, settings, today=first_monday + dt.timedelta(days=7))
    after = await assigned()
    assert before and after == before
    # У 5-А два уроки математики на 5 слотів тижня: лічильник від понеділка тижня запуску
    # (як було) дав би на цих датах інші уроки.
    math = {
        sid("lesson", lesson["key"]) for lesson in content.LESSONS if lesson["subject"] == "math"
    }
    assert len(math) == 2 and len(math & set(before.values())) == 2


async def test_seed_media_and_extra_content(db_session, seed_storage, monkeypatch) -> None:
    """Медіа демо-уроків: через справжнє сховище, з підписом, VTT, без дублів на повторі."""
    import datetime as dt

    from app.seed.runner import MEDIA_DIR, lessons_extra
    from app.services import packs as packs_service

    settings = get_settings()
    today = dt.date(2026, 11, 24)  # вівторок
    monkeypatch.setattr(
        packs_service, "_now", lambda: dt.datetime(2026, 11, 24, 6, 0, tzinfo=dt.UTC)
    )
    result = await seed(db_session, settings, today=today, password="demo-password-42")
    assert result.problems == {}
    sources = sorted(p.name for p in MEDIA_DIR.iterdir() if p.suffix != ".md")
    media = (await db_session.scalars(select(MediaAsset))).all()
    assert sorted(m.id for m in media) == sorted(sid("media", name) for name in sources)
    files = {p.name for p in seed_storage.root.rglob("*") if p.is_file()}
    assert len(files) == len(sources)
    teachers = {sid("user", "teacher5a"), sid("user", "teacher7b")}
    by_id = {m.id: m for m in media}
    for m in media:
        assert m.uploaded_by in teachers and m.processing_status == "ready" and m.attribution
    # Зображення перекодовані у WebP (або лишились меншим оригіналом), відео з субтитрами.
    abacus = by_id[sid("media", "5-math-abacus.jpg")]
    assert abacus.mime_type == "image/webp"
    assert abacus.attribution == "Автор: Syced · CC0 · Wikimedia Commons"
    assert abacus.source_url.startswith("https://commons.wikimedia.org/wiki/File:")
    own = by_id[sid("media", "7-alg-balance.png")]
    assert own.attribution == "Автор: ShelterED team · CC BY 4.0" and own.source_url is None
    iss = by_id[sid("media", "7-phys-iss-earth.mp4")]
    assert iss.kind == "video" and iss.subtitles_id == sid("media", "7-phys-iss-earth.vtt")

    # Нові модулі, картки з медіа, пояснення й питання text/match.
    fractions = sid("lesson", "5-math-fractions")
    titles = (
        await db_session.scalars(
            select(Module.title)
            .where(Module.lesson_id == fractions, Module.part == "main")
            .order_by(Module.position)
        )
    ).all()
    assert titles[-1] == "Частина від числа"
    media_cards = await db_session.scalar(
        select(func.count()).select_from(Card).where(Card.media_asset_id.is_not(None))
    )
    expected = sum(
        1 for v in lessons_extra().values() for card in v["cards"] if card["kind"] != "text"
    )
    assert media_cards == expected
    kinds = set((await db_session.scalars(select(Question.kind))).all())
    assert kinds == {"single", "multiple", "text", "match"}
    explained = await db_session.scalar(
        select(func.count()).select_from(Question).where(Question.explanation.is_not(None))
    )
    assert explained == await db_session.scalar(select(func.count()).select_from(Question))

    # Маніфест «Рюкзака» несе підпис медіа (медіа — на сьогодні й завтра).
    klass = await db_session.get(SchoolClass, sid("class", "7b"))
    manifest = await packs_service.manifest(db_session, klass, None, None, seed_storage)
    assert manifest.media and all(item.attribution for item in manifest.media)

    # Повтор: нічого не дублюється, файл, якого не стало у сховищі, відновлюється.
    before = await counts(db_session)
    lost = seed_storage.local_path(abacus.storage_key)
    lost.unlink()
    await seed(db_session, settings, today=today, password="demo-password-42")
    assert await counts(db_session) == before
    assert lost.is_file()
    assert len({p.name for p in seed_storage.root.rglob("*") if p.is_file()}) == len(sources)
