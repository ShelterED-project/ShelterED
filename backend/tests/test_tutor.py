"""ШІ-репетитор (B13): `POST /tutor/ask`, клієнт AI-сервісу, закешовані пояснення для пакета.

Справжніх мережевих викликів немає: AI-сервіс підміняє `httpx.MockTransport`.
"""

import base64
import datetime as dt
import gzip
import json
import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from conftest import auth_header
from sqlalchemy import select

from app.api.tutor import get_ai_client
from app.core.config import get_settings
from app.models.lessons import Card, Lesson, Module
from app.models.school import LessonAssignment, ScheduleSlot
from app.models.tutor import TutorConversation, TutorExplanation
from app.services import packs as packs_service
from app.services import retention as retention_service
from app.services import tutor as service
from app.services.ai import AIClient
from app.workers import tutor as tutor_worker
from app.workers.celery_app import celery_app

pytestmark = pytest.mark.anyio


AI_URL = "http://ai.test"
AI_KEY = "internal-key-for-tests"
CARD_TEXT = "**Дріб** — частина цілого. У дробі 3/4 знаменник 4."
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
TASK = {
    "task_id": "g-1",
    "question": "Знайди 20% від числа 150.",
    "answer_type": "number",
    "answer": "30",
    "expected_answer": "30",
    "difficulty": 2,
    "hints": ["20% — це 0,2", "150 · 0,2", "= 30"],
    "common_mistakes": [{"wrong": "3000", "error_type": "x", "feedback": "y"}],
}


def reply(intent: str = "explain", **kw: Any) -> dict[str, Any]:
    return {
        "reply": kw.pop("text", f"Відповідь ({intent})"),
        "intent": intent,
        "topic_id": None,
        "task": kw.pop("task", None),
        "hints_used": kw.pop("hints_used", 0),
        "check_result": kw.pop("check_result", None),
        "suggestions": kw.pop("suggestions", ["💡 Дай підказку"]),
    }


class FakeAI:
    """AI-сервіс: записує запити, відповідає з черги (або однією відповіддю за замовчуванням)."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.responses: list[Callable[[httpx.Request], httpx.Response] | dict] = []
        self.default: dict[str, Any] = reply()

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        item = self.responses.pop(0) if self.responses else self.default
        if callable(item):
            return item(request)
        return httpx.Response(200, json=item)

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]

    def client(self) -> AIClient:
        return AIClient(AI_URL, AI_KEY, transport=httpx.MockTransport(self.handler))


@pytest.fixture
def ai(app) -> FakeAI:
    fake = FakeAI()
    app.dependency_overrides[get_ai_client] = fake.client
    return fake


@pytest.fixture
async def course(factory, world) -> SimpleNamespace:
    """7-А: сьогодні опублікований урок «Дроби» (модуль із текстовою карткою);
    7-Б: свій урок, недоступний учню 7-А."""
    db = factory.session
    c = SimpleNamespace()
    c.subject = await factory.subject()
    c.day = dt.datetime.now(dt.UTC).astimezone(ZoneInfo("Europe/Kyiv")).date()

    async def lesson(klass, title: str) -> tuple[Lesson, Module, Card]:
        les = Lesson(
            subject_id=c.subject.id,
            author_id=world.teacher_a.id,
            title=title,
            shelter_part="Укриття",
            main_part="Основна",
            status="published",
            published_at=dt.datetime.now(dt.UTC),
        )
        db.add(les)
        await db.flush()
        mod = Module(
            lesson_id=les.id, part="shelter", position=1, title=f"{title}: що це", duration_min=4
        )
        db.add(mod)
        await db.flush()
        card = Card(module_id=mod.id, position=1, kind="text", body={"text": CARD_TEXT})
        db.add(card)
        for day in (c.day - dt.timedelta(days=1), c.day, c.day + dt.timedelta(days=1)):
            slot = ScheduleSlot(
                class_id=klass.id,
                subject_id=c.subject.id,
                weekday=day.isoweekday(),
                starts_at=dt.time(9, 0),
                ends_at=dt.time(9, 45),
                valid_from=c.day - dt.timedelta(days=7),
            )
            db.add(slot)
            await db.flush()
            db.add(LessonAssignment(slot_id=slot.id, date=day, lesson_id=les.id))
        await db.flush()
        return les, mod, card

    c.lesson, c.module, c.card = await lesson(world.class_a, "Дроби")
    c.other_lesson, c.other_module, _ = await lesson(world.class_b, "Відсотки")
    return c


def ask_body(**kw: Any) -> dict[str, Any]:
    body = {"request_id": str(uuid.uuid4()), "conversation_id": str(uuid.uuid4())}
    body.update({k: str(v) if isinstance(v, uuid.UUID) else v for k, v in kw.items()})
    return body


async def ask(client, world, body: dict, user=None) -> httpx.Response:
    return await client.post("/tutor/ask", json=body, headers=auth_header(user or world.student_a))


# ---------- запит до AI і відповідь учню ----------


async def test_explain_card_sends_context_and_key_without_personal_data(
    client, world, course, ai
) -> None:
    r = await ask(
        client, world, ask_body(action="explain", card_id=course.card.id, message="Не зрозумів")
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["reply"] == "Відповідь (explain)" and out["intent"] == "explain"
    assert out["cached"] is False and out["task"] is None and out["check_result"] is None

    (request,) = ai.requests
    assert str(request.url) == f"{AI_URL}/ai/v1/chat"
    assert request.headers["X-Internal-Key"] == AI_KEY
    sent = ai.bodies[0]
    assert sent["action"] == "explain" and sent["grade"] == 7
    assert sent["subject"] == "Математика"
    assert sent["topic"] == course.module.title and sent["topic_id"] == str(course.module.id)
    assert CARD_TEXT in sent["message"] and "Не зрозумів" in sent["message"]
    assert sent["history"] == [] and sent["hints_used"] == 0 and "task" not in sent
    # Ні імені, ні прізвища, ні школи, ні id учня.
    raw = request.content.decode()
    for secret in ("Іван", "Петренко", "Школа", str(world.student_a.id)):
        assert secret not in raw


async def test_card_text_is_capped(client, world, course, ai, db_session) -> None:
    course.card.body = {"text": "а" * 5000}
    await db_session.flush()
    r = await ask(client, world, ask_body(action="explain", card_id=course.card.id))
    assert r.status_code == 200
    message = ai.bodies[0]["message"]
    assert message.count("а") <= service.MAX_CONTEXT_CHARS + 5


async def test_task_answer_never_reaches_student(client, world, course, ai) -> None:
    ai.default = reply(
        "practice", task={**TASK, "options": ["30", "3000"], "solution": "секрет"}, hints_used=0
    )
    r = await ask(client, world, ask_body(action="practice", module_id=course.module.id))
    assert r.status_code == 200, r.text
    task = r.json()["task"]
    assert task == {
        "question": TASK["question"],
        "answer_type": "number",
        "options": ["30", "3000"],
    }
    raw = r.text
    for leaked in ('"answer"', "expected_answer", 'hints"', "common_mistakes", "секрет", "0,2"):
        assert leaked not in raw


async def test_task_and_hints_are_kept_and_sent_back(client, world, course, ai, db_session) -> None:
    conv_id = uuid.uuid4()
    ai.responses = [
        reply("practice", task=TASK, hints_used=0),
        reply("practice", task=TASK, hints_used=1, text="Підказка 1"),
        reply(
            "check",
            task=TASK,
            hints_used=1,
            check_result={"correct": False, "score": 0.0, "error_type": "x", "method": "llm"},
        ),
    ]
    first = await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="practice", module_id=course.module.id),
    )
    assert first.status_code == 200
    hint = await ask(client, world, ask_body(conversation_id=conv_id, action="practice"))
    assert hint.status_code == 200 and hint.json()["hints_used"] == 1
    check = await ask(
        client, world, ask_body(conversation_id=conv_id, action="check", message="3000")
    )
    assert check.status_code == 200
    assert check.json()["check_result"] == {"correct": False, "score": 0.0}

    second, third = ai.bodies[1], ai.bodies[2]
    # Контекст береться з розмови; AI отримує завдання з відповіддю й лічильник підказок.
    assert second["task"] == TASK and second["hints_used"] == 0
    assert second["topic_id"] == str(course.module.id)
    assert third["task"] == TASK and third["hints_used"] == 1 and third["message"] == "3000"
    assert len(third["history"]) == 4

    conv = await db_session.get(TutorConversation, conv_id, populate_existing=True)
    assert conv.student_id == world.student_a.id and conv.module_id == course.module.id
    assert conv.task == TASK and conv.hints_used == 1 and len(conv.history) == 6


async def test_correct_check_closes_task(client, world, course, ai, db_session) -> None:
    conv_id = uuid.uuid4()
    ai.responses = [
        reply("practice", task=TASK),
        reply("check", task=TASK, hints_used=0, check_result={"correct": True, "score": 1.0}),
    ]
    await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="practice", module_id=course.module.id),
    )
    r = await ask(client, world, ask_body(conversation_id=conv_id, action="check", message="30"))
    assert r.json()["check_result"] == {"correct": True, "score": 1.0}
    assert r.json()["task"] is None
    conv = await db_session.get(TutorConversation, conv_id, populate_existing=True)
    assert conv.task is None and conv.hints_used == 0


async def test_history_is_capped_at_8(client, world, course, ai, db_session) -> None:
    conv_id = uuid.uuid4()
    for i in range(6):
        r = await ask(
            client,
            world,
            ask_body(conversation_id=conv_id, module_id=course.module.id, message=f"питання {i}"),
        )
        assert r.status_code == 200
    assert [len(b["history"]) for b in ai.bodies] == [0, 2, 4, 6, 8, 8]
    assert ai.bodies[-1]["history"][0] == {"role": "user", "text": "питання 1"}
    conv = await db_session.get(TutorConversation, conv_id, populate_existing=True)
    assert len(conv.history) == 8 and conv.history[-2]["text"] == "питання 5"


async def test_same_request_id_returns_stored_reply_without_ai(client, world, course, ai) -> None:
    body = ask_body(module_id=course.module.id, message="Що таке дріб?")
    first = await ask(client, world, body)
    ai.default = reply(text="інша відповідь")
    again = await ask(client, world, body)
    assert first.status_code == again.status_code == 200
    assert again.json() == first.json()
    assert len(ai.requests) == 1


async def test_replay_does_not_spend_rate_limit(client, world, course, ai) -> None:
    body = ask_body(module_id=course.module.id, message="Що таке дріб?")
    assert (await ask(client, world, body)).status_code == 200
    for _ in range(get_settings().rate_limit_tutor + 5):
        assert (await ask(client, world, body)).status_code == 200
    assert len(ai.requests) == 1


async def test_safety_intent_returns_reply_and_stores_nothing_new(
    client, world, course, ai, db_session
) -> None:
    conv_id = uuid.uuid4()
    ai.responses = [
        reply("practice", task=TASK, hints_used=1),
        reply("safety", text="Підійди до дорослого. 116 111", task=None, suggestions=[]),
    ]
    await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="practice", module_id=course.module.id),
    )
    r = await ask(client, world, ask_body(conversation_id=conv_id, message="мені страшно"))
    assert r.status_code == 200
    out = r.json()
    assert out["intent"] == "safety" and out["task"] is None and out["suggestions"] == []
    assert "116 111" in out["reply"]
    conv = await db_session.get(TutorConversation, conv_id, populate_existing=True)
    assert conv.task == TASK and conv.hints_used == 1
    assert len(conv.history) == 2
    assert "мені страшно" not in json.dumps(conv.history, ensure_ascii=False)
    assert "мені страшно" not in json.dumps(conv.replies, ensure_ascii=False)


async def test_unknown_intent_is_shown_as_explain(client, world, course, ai) -> None:
    ai.default = reply("brand_new_intent")
    r = await ask(client, world, ask_body(module_id=course.module.id, message="?"))
    assert r.status_code == 200 and r.json()["intent"] == "explain"


async def test_check_without_task_is_rejected(client, world, course, ai) -> None:
    r = await ask(client, world, ask_body(action="check", module_id=course.module.id, message="30"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "TUTOR_TASK_REQUIRED"
    assert ai.requests == []


# ---------- фото ----------


async def _with_task(client, world, course, ai, conv_id) -> None:
    ai.responses = [reply("practice", task=TASK)]
    r = await ask(
        client,
        world,
        ask_body(conversation_id=conv_id, action="practice", module_id=course.module.id),
    )
    assert r.status_code == 200


async def test_photo_is_sent_as_data_url_with_longer_timeout(client, world, course, ai) -> None:
    conv_id = uuid.uuid4()
    await _with_task(client, world, course, ai, conv_id)
    ai.default = reply("check", task=TASK, check_result={"correct": True, "score": 1.0})
    image = base64.b64encode(PNG).decode()
    r = await ask(client, world, ask_body(conversation_id=conv_id, image_base64=image))
    assert r.status_code == 200, r.text
    sent = ai.bodies[-1]
    assert sent["action"] == "check" and sent["image_base64"] == f"data:image/png;base64,{image}"
    assert sent["task"] == TASK
    assert ai.requests[-1].extensions["timeout"]["read"] == get_settings().ai_image_timeout_s
    assert ai.requests[0].extensions["timeout"]["read"] == get_settings().ai_timeout_s


@pytest.mark.parametrize(
    "image",
    [
        base64.b64encode(b"GIF89a" + b"\x00" * 32).decode(),
        "not base64 at all!",
        "data:image/png;base64," + base64.b64encode(b"plain text").decode(),
    ],
    ids=["gif", "not-base64", "not-png"],
)
async def test_bad_photo_is_rejected(client, world, course, ai, image) -> None:
    conv_id = uuid.uuid4()
    await _with_task(client, world, course, ai, conv_id)
    r = await ask(client, world, ask_body(conversation_id=conv_id, image_base64=image))
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_IMAGE"
    assert len(ai.requests) == 1


async def test_too_large_photo_is_rejected(app, client, world, course, ai) -> None:
    conv_id = uuid.uuid4()
    await _with_task(client, world, course, ai, conv_id)
    small = get_settings().model_copy(update={"tutor_max_image_bytes": 100})
    app.dependency_overrides[get_settings] = lambda: small
    image = base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 200).decode()
    r = await ask(client, world, ask_body(conversation_id=conv_id, image_base64=image))
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_IMAGE"


async def test_photo_only_for_check(client, world, course, ai) -> None:
    image = base64.b64encode(PNG).decode()
    r = await ask(
        client,
        world,
        ask_body(action="explain", module_id=course.module.id, image_base64=image),
    )
    assert r.status_code == 422


async def test_body_limit_allows_photo_on_tutor_only(client, world) -> None:
    big = "A" * (2 * 1024 * 1024)
    r = await ask(client, world, ask_body(message="x", image_base64=big))
    # Тіло пройшло ліміт (далі — перевірка фото), а на інших шляхах 2 МБ — 413.
    assert r.status_code != 413
    other = await client.post("/sync/events", content=big, headers={**auth_header(world.student_a)})
    assert other.status_code == 413


# ---------- доступ ----------


async def test_lesson_of_other_class_is_forbidden(client, world, course, ai) -> None:
    for body in (
        ask_body(lesson_id=course.other_lesson.id, message="?"),
        ask_body(module_id=course.other_module.id, message="?"),
    ):
        r = await ask(client, world, body)
        assert r.status_code == 403, r.text
    assert (
        await ask(client, world, ask_body(lesson_id=uuid.uuid4(), message="?"))
    ).status_code == 404
    assert ai.requests == []


async def test_card_must_match_module(client, world, course, ai) -> None:
    r = await ask(client, world, ask_body(card_id=course.card.id, module_id=course.other_module.id))
    assert r.status_code == 422


async def test_conversation_of_other_student_is_not_found(client, world, factory, course, ai):
    classmate = await factory.student(world.class_a, "Олег", "Мельник")
    body = ask_body(module_id=course.module.id, message="?")
    assert (await ask(client, world, body)).status_code == 200
    # Чужа розмова: і новий запит, і повтор чужого request_id — 404, без виклику AI.
    for b in (
        {**body, "request_id": str(uuid.uuid4())},
        body,
    ):
        r = await ask(client, world, b, user=classmate)
        assert r.status_code == 404
    assert len(ai.requests) == 1


async def test_only_students(client, world, course, ai) -> None:
    for user in (world.teacher_a, world.parent_a, world.admin):
        r = await ask(client, world, ask_body(message="?"), user=user)
        assert r.status_code == 403
    assert (await client.post("/tutor/ask", json=ask_body(message="?"))).status_code == 401


# ---------- збої AI ----------


def status(code: int, body: Any = None) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(code, json=body)


def raises(exc: type[Exception]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc("boom", request=request)

    return handler


@pytest.mark.parametrize(
    ("responses", "calls"),
    [
        ([raises(httpx.ConnectError)] * 2, 2),
        ([raises(httpx.ConnectTimeout)] * 2, 2),
        ([raises(httpx.ReadTimeout)], 1),
        ([status(500, {"code": "internal_error"})], 1),
        ([status(503, {"code": "model_unavailable"})], 1),
        ([status(404)], 1),
        ([status(401, {"code": "unauthorized"})], 1),
        ([lambda r: httpx.Response(200, content=b"<html>ngrok</html>")], 1),
        ([status(200, {"intent": "explain"})], 1),
    ],
    ids=[
        "connect",
        "connect-timeout",
        "read-timeout",
        "500",
        "503",
        "404-tunnel",
        "401",
        "not-json",
        "no-reply",
    ],
)
async def test_ai_failures_give_503(client, world, course, ai, responses, calls) -> None:
    ai.responses = list(responses)
    r = await ask(client, world, ask_body(module_id=course.module.id, message="?"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "AI_UNAVAILABLE"
    assert len(ai.requests) == calls


async def test_connect_error_is_retried_once(client, world, course, ai) -> None:
    ai.responses = [raises(httpx.ConnectError)]
    r = await ask(client, world, ask_body(module_id=course.module.id, message="?"))
    assert r.status_code == 200 and len(ai.requests) == 2


async def test_ai_422_maps_to_502_or_invalid_image(client, world, course, ai) -> None:
    ai.responses = [status(422, {"code": "topic_required", "message": "m", "details": None})]
    r = await ask(client, world, ask_body(module_id=course.module.id, message="?"))
    assert r.status_code == 502 and r.json()["error"]["code"] == "AI_BAD_REQUEST"
    ai.responses = [status(422, {"code": "invalid_image", "message": "m", "details": None})]
    r = await ask(client, world, ask_body(module_id=course.module.id, message="?"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_IMAGE"


async def test_ai_disabled_gives_503(client, world, course) -> None:
    r = await ask(client, world, ask_body(module_id=course.module.id, message="?"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "AI_UNAVAILABLE"


async def test_logs_have_no_key_and_no_child_text(client, world, course, ai, caplog) -> None:
    ai.responses = [status(401, {"code": "unauthorized", "message": "Invalid key"})]
    with caplog.at_level(logging.DEBUG):
        r = await ask(client, world, ask_body(module_id=course.module.id, message="таємниця"))
    assert r.status_code == 503
    assert any("AI_INTERNAL_KEY" in rec.getMessage() for rec in caplog.records)
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert AI_KEY not in text and "таємниця" not in text


async def test_ai_down_explain_falls_back_to_cached_explanation(
    client, world, course, ai, db_session
) -> None:
    db_session.add(
        TutorExplanation(
            lesson_id=course.lesson.id,
            lesson_version=course.lesson.version,
            module_id=course.module.id,
            text="Готове пояснення",
        )
    )
    await db_session.flush()
    ai.responses = [status(503, {"code": "model_unavailable"})]
    r = await ask(client, world, ask_body(action="explain", module_id=course.module.id))
    assert r.status_code == 200
    assert r.json()["reply"] == "Готове пояснення" and r.json()["cached"] is True


# ---------- закешовані пояснення для пакета ----------


@pytest.fixture
def worker(db_session, monkeypatch, ai) -> FakeAI:
    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr(tutor_worker, "standalone_session", session)
    monkeypatch.setattr(tutor_worker, "ai_client", ai.client)
    return ai


async def test_explanations_are_generated_and_included_in_pack(
    db_session, world, course, worker, enqueued
) -> None:
    worker.default = reply(text="Дріб — це як піца, поділена на частини.")
    assert course.lesson.id in await service.lessons_missing_explanations(db_session)

    created, failed = await tutor_worker._explain_lesson(course.lesson.id)
    assert (created, failed) == (1, False)
    sent = worker.bodies[0]
    assert sent["action"] == "explain" and CARD_TEXT in sent["message"]
    assert sent["topic_id"] == str(course.module.id)
    assert [e.name for e in enqueued] == ["packs.rebuild_for_lesson"]
    assert course.lesson.id not in await service.lessons_missing_explanations(db_session)

    # Повтор нічого не генерує.
    assert await tutor_worker._explain_lesson(course.lesson.id) == (0, False)
    assert len(worker.requests) == 1

    built = await packs_service.rebuild_class(db_session, world.class_a.id, get_settings())
    pack = next(p for p in built if p.pack_date == course.day)
    content = json.loads(gzip.decompress(pack.content_gzip))
    row = await db_session.scalar(select(TutorExplanation))
    assert content["explanations"] == [
        {
            "id": str(row.id),
            "lesson_id": str(course.lesson.id),
            "module_id": str(course.module.id),
            "text": "Дріб — це як піца, поділена на частини.",
        }
    ]


async def test_new_explanation_changes_pack_hash(db_session, world, course, worker) -> None:
    settings = get_settings()
    first = await packs_service.rebuild_class(db_session, world.class_a.id, settings)
    assert first
    await tutor_worker._explain_lesson(course.lesson.id)
    second = await packs_service.rebuild_class(db_session, world.class_a.id, settings)
    assert second and {p.content_hash for p in second}.isdisjoint(p.content_hash for p in first)


async def test_ai_down_keeps_explanations_for_retry(db_session, course, worker, enqueued) -> None:
    worker.responses = [raises(httpx.ConnectError)] * 2
    assert await tutor_worker._explain_lesson(course.lesson.id) == (0, True)
    assert await db_session.scalar(select(TutorExplanation)) is None
    assert enqueued == []
    assert course.lesson.id in await service.lessons_missing_explanations(db_session)


def test_explain_task_retries_later_when_ai_down(monkeypatch) -> None:
    async def down(lesson_id):
        return 0, True

    retried: dict[str, Any] = {}

    class Retry(Exception):
        pass

    def retry(**kw):
        retried.update(kw)
        return Retry()

    task = celery_app.tasks["tutor.explain_lesson"]
    monkeypatch.setattr(tutor_worker, "_explain_lesson", down)
    monkeypatch.setattr(task, "retry", retry)
    with pytest.raises(Retry):
        task.run(str(uuid.uuid4()))
    assert retried["countdown"] == tutor_worker.EXPLAIN_RETRY_COUNTDOWN_S
    assert task.max_retries * tutor_worker.EXPLAIN_RETRY_COUNTDOWN_S >= 24 * 3600


async def test_beat_picks_lessons_without_explanations(
    db_session, course, worker, enqueued
) -> None:
    assert await tutor_worker._explain_missing() == 2
    assert sorted(e.args[0] for e in enqueued if e.name == "tutor.explain_lesson") == sorted(
        [str(course.lesson.id), str(course.other_lesson.id)]
    )
    entry = celery_app.conf.beat_schedule["tutor-explain-missing"]
    assert entry["task"] == "tutor.explain_missing"


async def test_beat_and_task_skip_when_ai_disabled(db_session, course, monkeypatch, enqueued):
    monkeypatch.setattr(
        tutor_worker, "ai_client", lambda: AIClient("", "", transport=httpx.MockTransport(None))
    )
    assert await tutor_worker._explain_missing() == 0
    assert await tutor_worker._explain_lesson(course.lesson.id) == (0, False)
    assert enqueued == []


async def test_republished_lesson_needs_new_explanations(db_session, course, worker) -> None:
    await tutor_worker._explain_lesson(course.lesson.id)
    course.lesson.version += 1
    await db_session.flush()
    assert course.lesson.id in await service.lessons_missing_explanations(db_session)
    await tutor_worker._explain_lesson(course.lesson.id)
    rows = list(await db_session.scalars(select(TutorExplanation)))
    assert [r.lesson_version for r in rows] == [course.lesson.version]


# ---------- строк зберігання ----------


async def test_old_conversations_are_purged(db_session, world) -> None:
    now = dt.datetime.now(dt.UTC)
    old = TutorConversation(id=uuid.uuid4(), student_id=world.student_a.id)
    fresh = TutorConversation(id=uuid.uuid4(), student_id=world.student_a.id)
    db_session.add_all([old, fresh])
    await db_session.flush()
    old.updated_at = now - dt.timedelta(days=31)
    await db_session.flush()
    counts = await retention_service.purge(db_session, get_settings(), now)
    assert counts["tutor_conversations"] == 1
    assert await db_session.get(TutorConversation, fresh.id) is not None
