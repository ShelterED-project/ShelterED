"""Демо-дані (`python -m app.cli seed`): ідемпотентність, перевірки публікації, охорона prod."""

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app import cli
from app.core.config import get_settings
from app.core.security import verify_secret
from app.models.alerts import AlertEvent
from app.models.lessons import Card, Lesson, Module, Question, Subject, Test
from app.models.packs import KnowledgePack
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
    third = await seed(db_session, settings, password="demo-password-42")
    assert third.passwords_set and third.generated_password is None
    assert await counts(db_session) == after_first
    await db_session.refresh(admin)
    assert verify_secret("demo-password-42", admin.password_hash)
    assert admin.token_version == 1


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
        assert 2 <= len(modules) <= 3
        assert all(3 <= m.duration_min <= 5 for m in modules)
        test = await db_session.scalar(select(Test).where(Test.lesson_id == lesson.id))
        n = await db_session.scalar(
            select(func.count()).select_from(Question).where(Question.test_id == test.id)
        )
        assert 4 <= n <= 6
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

    async def fake_seed(session, settings, password=None):
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
