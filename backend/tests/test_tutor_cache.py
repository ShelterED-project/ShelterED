"""Кеш пояснень ШІ за вмістом (B13.3): ключ, повторне використання, онлайн-кеш, Celery, пакет.

Шари: L1 — ключ; L2 — сервіс і БД (`POST /tutor/ask`, повторна публікація, копія, чистка);
L3 — Celery-задачі; L4 — пакет «Рюкзак». Справжніх мережевих викликів немає: AI підміняє
`httpx.MockTransport`, Redis — фейки в пам'яті.
"""

import asyncio
import datetime as dt
import gzip
import json
import uuid
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import test_tutor as shared
from conftest import auth_header
from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.api.tutor import get_ai_client
from app.core.config import get_settings
from app.models.lessons import Card, Lesson, Module, Question, Subject, Test
from app.models.packs import KnowledgePack
from app.models.school import LessonAssignment, ScheduleSlot
from app.models.tutor import TutorConversation, TutorExplanation, TutorExplanationAttempt
from app.schemas.lessons import LessonCopy
from app.services import lessons as lessons_service
from app.services import packs as packs_service
from app.services import retention as retention_service
from app.services import tutor as service
from app.workers import tutor as tutor_worker

pytestmark = pytest.mark.anyio

# Фікстури й помічники test_tutor (курс, фейковий AI, фейкові Redis).
ai, course, worker = shared.ai, shared.course, shared.worker
fake_redis, lock_redis = shared.fake_redis, shared.lock_redis
CARD_TEXT, FakeAI, FakeAsyncRedis = shared.CARD_TEXT, shared.FakeAI, shared.FakeAsyncRedis
ask, ask_body, module_key = shared.ask, shared.ask_body, shared.module_key
raises, reply = shared.raises, shared.reply

EXPLANATION = "Дріб — це як піца, поділена на частини."


def key_of(**kw: Any) -> str | None:
    base: dict[str, Any] = {
        "grade": 7,
        "subject": "Математика",
        "title": "Дроби: що це",
        "texts": ["Перший абзац.", "Другий абзац."],
        "prompt_version": "1",
    }
    base.update(kw)
    return service.explanation_key(**base)


async def current_key(db_session, c) -> str:
    return await module_key(db_session, c.lesson, c.module)


async def explanations(db_session) -> list[TutorExplanation]:
    return list(await db_session.scalars(select(TutorExplanation)))


async def pack_of(db_session, klass, day) -> tuple[KnowledgePack, dict[str, Any]]:
    """Перезбирає пакети класу; найновіша версія дня та її вміст."""
    await packs_service.rebuild_class(db_session, klass.id, get_settings())
    pack = await packs_service.latest_pack(db_session, klass.id, day)
    raw = await db_session.scalar(
        select(KnowledgePack.content_gzip).where(KnowledgePack.id == pack.id)
    )
    return pack, json.loads(gzip.decompress(raw))


# ================= L1: ключ =================


def test_key_ignores_whitespace_and_dict_order() -> None:
    a = key_of()
    assert a is not None and len(a) == 64
    assert a == key_of(texts=["  Перший\n абзац. ", "Другий\t\tабзац.", "   "])
    assert a == key_of(title="  Дроби:   що це ")
    assert a == service.explanation_key(
        prompt_version="1",
        texts=["Перший абзац.", "Другий абзац."],
        title="Дроби: що це",
        subject="Математика",
        grade=7,
    )
    assert key_of(texts=["", "  "]) is None


@pytest.mark.parametrize(
    "change",
    [
        {"grade": 8},
        {"subject": "Фізика"},
        {"title": "Дроби: приклади"},
        {"texts": ["Перший абзац.", "Другий абзац!"]},
        {"texts": ["Другий абзац.", "Перший абзац."]},
        {"prompt_version": "2"},
    ],
)
def test_key_changes_with_what_the_llm_sees(change) -> None:
    assert key_of(**change) != key_of()


async def test_key_ignores_irrelevant_lesson_edits(db_session, world, course) -> None:
    before = await current_key(db_session, course)
    les, mod = course.lesson, course.module
    les.shelter_part, les.main_part, les.title = "Інший опис", "Інша основна", "Нова назва"
    les.version += 1
    mod.position, mod.duration_min = 5, 3
    course.card.position = 10
    db_session.add(Card(module_id=mod.id, position=11, kind="image", body={"caption": "Піца"}))
    db_session.add(Card(module_id=mod.id, position=12, kind="text", body={"text": "   "}))
    test = Test(lesson_id=les.id, title="Тест")
    db_session.add(test)
    await db_session.flush()
    db_session.add(
        Question(
            test_id=test.id,
            position=1,
            kind="single",
            prompt="?",
            options=[{"id": "a", "text": "1"}],
            answer_key=["a"],
        )
    )
    await db_session.flush()
    assert await current_key(db_session, course) == before


@pytest.mark.parametrize("what", ["title", "text", "grade", "subject", "prompt"])
async def test_key_changes_with_relevant_edits(
    db_session, world, course, factory, monkeypatch, what
) -> None:
    before = await current_key(db_session, course)
    if what == "title":
        course.module.title = "Дроби: інакше"
    elif what == "text":
        course.card.body = {"text": CARD_TEXT + " Доповнення."}
    elif what == "grade":
        course.lesson.grade = 8
    elif what == "subject":
        course.lesson.subject_id = (await factory.subject(name="Алгебра")).id
    else:
        monkeypatch.setattr(get_settings(), "tutor_prompt_version", "2")
    await db_session.flush()
    assert await current_key(db_session, course) != before


async def test_online_key_matches_pack_key(db_session, world, course) -> None:
    """Онлайн «Поясни» модуля (клас учня) і пакет (клас уроку) рахують той самий ключ."""
    online = service.explanation_key(
        grade=world.class_a.grade,
        subject="Математика",
        title=course.module.title,
        texts=await service.module_texts(db_session, course.module.id),
        prompt_version=get_settings().tutor_prompt_version,
    )
    assert online == await current_key(db_session, course)


# ================= L2: сервіс і БД =================


async def test_republish_and_copy_reuse_explanation_without_llm(
    db_session, world, course, worker, enqueued
) -> None:
    # Клас уроку вказано (його успадковує копія); збігається з класом розкладу — ключ той самий.
    course.lesson.grade = 7
    worker.default = reply(text=EXPLANATION)
    assert await tutor_worker._explain_lesson(course.lesson.id) == (1, False)
    assert len(worker.requests) == 1

    # Повторна публікація з тим самим вмістом.
    course.lesson.version += 1
    course.lesson.shelter_part = "Новий опис"
    await db_session.flush()
    assert await tutor_worker._explain_lesson(course.lesson.id) == (0, False)

    # Копія уроку (колега) після публікації.
    copy, _ = await lessons_service.copy_lesson(
        db_session, world.teacher_b, course.lesson, LessonCopy(id=uuid.uuid4())
    )
    copy.status, copy.published_at = "published", dt.datetime.now(dt.UTC)
    await db_session.flush()
    assert copy.id not in await service.lessons_missing_explanations(db_session)
    assert await tutor_worker._explain_lesson(copy.id) == (0, False)
    assert len(worker.requests) == 1
    assert len(await explanations(db_session)) == 1


async def test_first_explain_is_shared_then_cached_for_others(
    client, world, course, ai, db_session, lock_redis
) -> None:
    ai.default = reply(text=EXPLANATION)
    first = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert first.status_code == 200 and first.json()["cached"] is False
    (row,) = await explanations(db_session)
    assert row.text == EXPLANATION and row.cache_key == await current_key(db_session, course)
    assert lock_redis.data == {}  # замок знято

    other = await ask(
        client, world, ask_body(action="explain", module_id=course.module.id), world.student_a
    )
    assert other.status_code == 200
    assert other.json()["reply"] == EXPLANATION and other.json()["cached"] is True
    assert len(ai.requests) == 1
    conv = await db_session.get(
        TutorConversation, uuid.UUID(other.json()["conversation_id"]), populate_existing=True
    )
    assert conv.explained_keys == [row.cache_key] and len(conv.history) == 2


async def test_pack_explanation_serves_online_explain(
    client, world, course, ai, worker, db_session
) -> None:
    worker.default = reply(text=EXPLANATION)
    await tutor_worker._explain_lesson(course.lesson.id)
    calls = len(ai.requests)
    r = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert r.json()["reply"] == EXPLANATION and r.json()["cached"] is True
    assert len(ai.requests) == calls


async def test_second_explain_in_same_conversation_calls_llm_and_keeps_cache(
    client, world, course, ai, db_session
) -> None:
    db_session.add(
        TutorExplanation(
            cache_key=await current_key(db_session, course), prompt_version="1", text=EXPLANATION
        )
    )
    await db_session.flush()
    conv_id = uuid.uuid4()
    ai.default = reply(text="Зовсім інше пояснення")
    first = await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="explain", module_id=course.module.id),
    )
    assert first.json()["cached"] is True and ai.requests == []
    again = await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="explain", module_id=course.module.id),
    )
    assert again.json()["cached"] is False and again.json()["reply"] == "Зовсім інше пояснення"
    assert len(ai.requests) == 1
    # AI бачить історію (пояснення з кешу) — і дає інше; спільний кеш не змінюється.
    assert ai.bodies[0]["history"][-1]["text"] == EXPLANATION
    (row,) = await explanations(db_session)
    assert row.text == EXPLANATION


@pytest.mark.parametrize(
    "body",
    [
        {"action": "explain", "message": "Не зрозумів, поясни"},
        {"action": "practice"},
        {"message": "Що таке дріб?"},
    ],
)
async def test_free_text_and_practice_are_never_cached(
    client, world, course, ai, db_session, body
) -> None:
    for _ in range(2):
        r = await ask(client, world, ask_body(module_id=course.module.id, **body))
        assert r.status_code == 200 and r.json()["cached"] is False
    assert len(ai.requests) == 2
    assert await explanations(db_session) == []


async def test_check_is_never_cached(client, world, course, ai, db_session) -> None:
    conv_id = uuid.uuid4()
    ai.responses = [reply("practice", task={"question": "1+1?", "answer": "2"})]
    ai.default = reply("check", check_result={"correct": False, "score": 0.0})
    await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="practice", module_id=course.module.id),
    )
    r = await ask(client, world, ask_body(conversation_id=conv_id, action="check", message="3"))
    assert r.status_code == 200
    assert await explanations(db_session) == []


async def test_safety_reply_is_never_cached(client, world, course, ai, db_session) -> None:
    ai.default = reply("safety", text="Звернись до дорослого")
    for _ in range(2):
        r = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
        assert r.json()["intent"] == "safety" and r.json()["cached"] is False
    assert len(ai.requests) == 2
    assert await explanations(db_session) == []
    conv = await db_session.get(
        TutorConversation, uuid.UUID(r.json()["conversation_id"]), populate_existing=True
    )
    assert conv.explained_keys == []


async def test_card_explain_is_cached_per_card_text(client, world, course, ai, db_session) -> None:
    ai.default = reply(text=EXPLANATION)
    await ask(client, world, ask_body(action="explain", card_id=course.card.id))
    r = await ask(client, world, ask_body(action="explain", card_id=course.card.id))
    assert r.json()["cached"] is True and len(ai.requests) == 1
    # Модуль з однією текстовою карткою: ключ картки й модуля той самий (і пакет його візьме).
    (row,) = await explanations(db_session)
    assert row.cache_key == await current_key(db_session, course)


async def test_new_shared_explanation_rebuilds_packs_of_lessons_with_that_key(
    client, world, course, ai, enqueued
) -> None:
    ai.default = reply(text=EXPLANATION)
    await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    rebuilds = [e.args[0] for e in enqueued if e.name == "packs.rebuild_for_lesson"]
    assert rebuilds == [str(course.lesson.id)]
    # Кеш-відповідь перезбірки не ставить.
    await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert len([e for e in enqueued if e.name == "packs.rebuild_for_lesson"]) == 1


async def test_lock_held_by_other_request_waits_for_its_answer(
    client, world, course, ai, db_session, monkeypatch
) -> None:
    key = await current_key(db_session, course)

    class OtherRequest(FakeAsyncRedis):
        """Замок тримає інший запит; на третій перевірці він зберігає пояснення й знімає
        замок (послідовно, без паралельного доступу до тестової сесії)."""

        checks = 0

        async def exists(self, name):
            self.checks += 1
            if self.checks == 3:
                db_session.add(
                    TutorExplanation(cache_key=key, prompt_version="1", text=EXPLANATION)
                )
                await db_session.flush()
                self.data.clear()
            return await super().exists(name)

    redis = OtherRequest()
    redis.data[service.explain_lock_name(key)] = "other"
    monkeypatch.setattr(service, "explain_lock_redis", lambda settings: redis)
    monkeypatch.setattr(service, "EXPLAIN_WAIT_POLL_S", 0.01)
    r = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert r.json()["reply"] == EXPLANATION and r.json()["cached"] is True
    assert ai.requests == [] and redis.checks == 3


async def test_lock_released_without_answer_falls_back_to_llm(
    client, world, course, ai, db_session, lock_redis, monkeypatch
) -> None:
    key = await current_key(db_session, course)
    lock_redis.data[service.explain_lock_name(key)] = "other"
    monkeypatch.setattr(service, "EXPLAIN_WAIT_POLL_S", 0.01)
    asyncio.get_running_loop().call_later(0.05, lock_redis.data.clear)
    r = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert r.status_code == 200 and r.json()["cached"] is False
    assert len(ai.requests) == 1


async def test_redis_down_still_answers(client, world, course, ai, monkeypatch) -> None:
    class Down:
        async def set(self, *a, **kw):
            raise RedisError("down")

    monkeypatch.setattr(service, "explain_lock_redis", lambda settings: Down())
    r = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert r.status_code == 200 and len(ai.requests) == 1


async def committed_course(committed) -> SimpleNamespace:
    f = committed.factory
    db = committed.session
    c = SimpleNamespace()
    school = await f.school()
    klass = await f.klass(school)
    teacher = await f.teacher(school, klass)
    c.students = [await f.student(klass, f"Учень{i}", "Тест") for i in range(5)]
    subject = await f.subject()
    lesson = Lesson(
        subject_id=subject.id,
        author_id=teacher.id,
        title="Дроби",
        shelter_part="У",
        main_part="О",
        status="published",
        published_at=dt.datetime.now(dt.UTC),
        grade=7,
    )
    db.add(lesson)
    await db.flush()
    c.module = Module(
        lesson_id=lesson.id, part="shelter", position=1, title="Що це", duration_min=4
    )
    db.add(c.module)
    await db.flush()
    db.add(Card(module_id=c.module.id, position=1, kind="text", body={"text": CARD_TEXT}))
    day = dt.datetime.now(dt.UTC).astimezone(ZoneInfo("Europe/Kyiv")).date()
    slot = ScheduleSlot(
        class_id=klass.id,
        subject_id=subject.id,
        weekday=day.isoweekday(),
        starts_at=dt.time(9, 0),
        ends_at=dt.time(9, 45),
        valid_from=day - dt.timedelta(days=7),
    )
    db.add(slot)
    await db.flush()
    db.add(LessonAssignment(slot_id=slot.id, date=day, lesson_id=lesson.id))
    await db.commit()
    return c


async def test_concurrent_first_explains_call_llm_once(committed, lock_redis, monkeypatch) -> None:
    """Клас з 5 учнів одночасно тисне «Поясни»: один виклик LLM, решта — з кешу."""
    c = await committed_course(committed)
    monkeypatch.setattr(service, "EXPLAIN_WAIT_POLL_S", 0.02)
    calls: list[httpx.Request] = []

    async def slow(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        await asyncio.sleep(0.3)
        return httpx.Response(200, json=reply(text=EXPLANATION))

    fake = FakeAI()
    fake.handler = slow  # type: ignore[method-assign]
    committed.app.dependency_overrides[get_ai_client] = fake.client

    async def one(student) -> httpx.Response:
        return await committed.client.post(
            "/tutor/ask",
            json=ask_body(action="explain", module_id=c.module.id),
            headers=auth_header(student),
        )

    results = await asyncio.gather(*(one(s) for s in c.students))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert {r.json()["reply"] for r in results} == {EXPLANATION}
    assert sorted(r.json()["cached"] for r in results) == [False] + [True] * 4
    assert len(calls) == 1
    async with committed.maker() as db:
        assert await db.scalar(select(func.count()).select_from(TutorExplanation)) == 1


async def test_purge_removes_only_unused_and_unreferenced(db_session, course, monkeypatch) -> None:
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    old = now - dt.timedelta(days=settings.retention_tutor_explanation_days + 1)
    referenced = await current_key(db_session, course)
    rows = {
        "referenced_old": TutorExplanation(
            cache_key=referenced, prompt_version="1", text="a", last_used_at=old
        ),
        "orphan_old": TutorExplanation(
            cache_key="0" * 64, prompt_version="1", text="b", last_used_at=old
        ),
        "orphan_recent": TutorExplanation(cache_key="1" * 64, prompt_version="1", text="c"),
    }
    db_session.add_all(rows.values())
    db_session.add_all(
        [
            TutorExplanationAttempt(cache_key="2" * 64, attempts=3, last_attempt_at=old),
            TutorExplanationAttempt(cache_key="3" * 64, attempts=1),
        ]
    )
    await db_session.flush()

    counts = await retention_service.purge(db_session, settings, now)
    assert counts["tutor_explanations"] == 1 and counts["tutor_explanation_attempts"] == 1
    left = {e.text for e in await explanations(db_session)}
    assert left == {"a", "c"}

    # Нова версія промпту: старий ключ модуля більше нікому не потрібен.
    monkeypatch.setattr(settings, "tutor_prompt_version", "2")
    counts = await retention_service.purge(db_session, settings, now)
    assert counts["tutor_explanations"] == 1
    assert {e.text for e in await explanations(db_session)} == {"c"}


async def test_cache_hit_touches_last_used_at(client, world, course, ai, db_session) -> None:
    old = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    row = TutorExplanation(
        cache_key=await current_key(db_session, course),
        prompt_version="1",
        text=EXPLANATION,
        last_used_at=old,
    )
    db_session.add(row)
    await db_session.flush()
    await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    await db_session.refresh(row)
    assert row.last_used_at > old + dt.timedelta(days=29)


# ================= L3: Celery =================


async def test_ai_down_counts_no_attempts_and_retries(db_session, course, worker) -> None:
    for _ in range(service.MAX_EXPLANATION_ATTEMPTS + 1):
        worker.responses = [raises(httpx.ConnectError)] * 2
        assert await tutor_worker._explain_lesson(course.lesson.id, retry=True) == (0, True)
    assert await db_session.scalar(select(TutorExplanationAttempt)) is None
    # AI повернувся: пояснення генерується один раз.
    worker.default = reply(text=EXPLANATION)
    assert await tutor_worker._explain_lesson(course.lesson.id, retry=True) == (1, False)
    assert await tutor_worker._explain_lesson(course.lesson.id) == (0, False)
    assert len(worker.requests) == (service.MAX_EXPLANATION_ATTEMPTS + 1) * 2 + 1
    assert len(await explanations(db_session)) == 1


async def test_key_lock_held_online_skips_module(db_session, course, worker, fake_redis) -> None:
    key = await current_key(db_session, course)
    fake_redis.data[service.explain_lock_name(key)] = "online"
    assert await tutor_worker._explain_lesson(course.lesson.id) == (0, False)
    assert worker.requests == []
    assert await db_session.scalar(select(TutorExplanationAttempt)) is None
    # Ключ і далі відсутній — beat добере.
    assert course.lesson.id in await service.lessons_missing_explanations(db_session)


async def test_worker_releases_key_lock(db_session, course, worker, fake_redis) -> None:
    await tutor_worker._explain_lesson(course.lesson.id)
    assert not any(k.startswith("tutor:explain:key:") for k in fake_redis.data)


async def test_attempt_limit_is_per_key_shared_by_copies(db_session, world, course, worker) -> None:
    course.lesson.grade = 7
    worker.default = reply("safety")
    for _ in range(service.MAX_EXPLANATION_ATTEMPTS):
        await tutor_worker._explain_lesson(course.lesson.id)
    (attempt,) = await db_session.scalars(select(TutorExplanationAttempt))
    assert attempt.cache_key == await current_key(db_session, course)
    assert attempt.attempts == service.MAX_EXPLANATION_ATTEMPTS
    copy, _ = await lessons_service.copy_lesson(
        db_session, world.teacher_a, course.lesson, LessonCopy(id=uuid.uuid4())
    )
    copy.status = "published"
    await db_session.flush()
    calls = len(worker.requests)
    assert copy.id not in await service.lessons_missing_explanations(db_session)
    assert await tutor_worker._explain_lesson(copy.id) == (0, False)
    assert len(worker.requests) == calls


async def test_new_prompt_version_regenerates(db_session, course, worker, monkeypatch) -> None:
    await tutor_worker._explain_lesson(course.lesson.id)
    monkeypatch.setattr(get_settings(), "tutor_prompt_version", "2")
    assert course.lesson.id in await service.lessons_missing_explanations(db_session)
    assert await tutor_worker._explain_lesson(course.lesson.id) == (1, False)
    assert {e.prompt_version for e in await explanations(db_session)} == {"1", "2"}


async def test_two_modules_with_same_content_get_one_llm_call(db_session, course, worker) -> None:
    twin = Module(
        lesson_id=course.lesson.id,
        part="main",
        position=1,
        title=course.module.title,
        duration_min=4,
    )
    db_session.add(twin)
    await db_session.flush()
    db_session.add(Card(module_id=twin.id, position=1, kind="text", body={"text": CARD_TEXT}))
    await db_session.flush()
    assert await tutor_worker._explain_lesson(course.lesson.id) == (1, False)
    assert len(worker.requests) == 1


# ================= L4: пакет =================


async def test_pack_includes_explanations_per_module_and_omits_missing(
    db_session, world, course, worker
) -> None:
    second = Module(
        lesson_id=course.lesson.id, part="main", position=1, title="Приклади", duration_min=4
    )
    db_session.add(second)
    await db_session.flush()
    db_session.add(Card(module_id=second.id, position=1, kind="text", body={"text": "3/4 + 1/4"}))
    await db_session.flush()

    worker.responses = [
        reply(text=EXPLANATION),
        raises(httpx.ConnectError),
        raises(httpx.ConnectError),
    ]
    assert await tutor_worker._explain_lesson(course.lesson.id) == (1, True)
    pack1, content = await pack_of(db_session, world.class_a, course.day)
    assert [e["module_id"] for e in content["explanations"]] == [str(course.module.id)]

    # Без змін — та сама версія.
    pack_same, _ = await pack_of(db_session, world.class_a, course.day)
    assert (pack_same.id, pack_same.content_hash) == (pack1.id, pack1.content_hash)

    worker.default = reply(text="Приклад: чверть піци")
    assert await tutor_worker._explain_lesson(course.lesson.id, retry=True) == (1, False)
    pack2, content = await pack_of(db_session, world.class_a, course.day)
    assert pack2.version == pack1.version + 1 and pack2.content_hash != pack1.content_hash
    assert [e["module_id"] for e in content["explanations"]] == [
        str(course.module.id),
        str(second.id),
    ]


async def test_touching_explanation_does_not_change_pack_hash(
    db_session, world, course, worker
) -> None:
    await tutor_worker._explain_lesson(course.lesson.id)
    pack1, _ = await pack_of(db_session, world.class_a, course.day)
    (row,) = await explanations(db_session)
    row.last_used_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=10)
    await db_session.flush()
    pack2, _ = await pack_of(db_session, world.class_a, course.day)
    assert pack2.id == pack1.id
    await db_session.refresh(row)
    assert row.last_used_at > dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)


async def test_republish_keeps_explanation_in_first_rebuilt_pack(
    db_session, world, course, worker
) -> None:
    worker.default = reply(text=EXPLANATION)
    await tutor_worker._explain_lesson(course.lesson.id)
    pack1, _ = await pack_of(db_session, world.class_a, course.day)

    # Повторна публікація без змін модуля (змінено лише опис уроку): перша ж перезбірка.
    course.lesson.version += 1
    course.lesson.main_part = "Оновлена основна частина"
    await db_session.flush()
    pack2, content = await pack_of(db_session, world.class_a, course.day)
    assert pack2.version == pack1.version + 1
    assert content["lessons"][0]["version"] == course.lesson.version
    assert [e["text"] for e in content["explanations"]] == [EXPLANATION]
    assert len(worker.requests) == 1


async def test_changed_module_drops_explanation_until_regenerated(
    db_session, world, course, worker
) -> None:
    await tutor_worker._explain_lesson(course.lesson.id)
    course.card.body = {"text": "Інший зміст"}
    course.lesson.version += 1
    await db_session.flush()
    _, content = await pack_of(db_session, world.class_a, course.day)
    assert content["explanations"] == []


async def test_pack_of_class_with_other_subject_name(db_session, world, course, worker) -> None:
    """Предмет — частина ключа: урок іншого предмета з тим самим текстом має власне
    пояснення."""
    await tutor_worker._explain_lesson(course.lesson.id)
    physics = Subject(name="Фізика")
    db_session.add(physics)
    await db_session.flush()
    course.lesson.subject_id = physics.id
    await db_session.flush()
    _, content = await pack_of(db_session, world.class_a, course.day)
    assert content["explanations"] == []
