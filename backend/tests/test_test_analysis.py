"""AI-аналіз тесту класу: запуск кнопкою вчителя, Celery-задача з фейковим AI, псевдоніми
замість id учнів, правки, публікація, фідбек учню/батькам і права доступу.

Справжніх мережевих викликів немає: AI-сервіс підміняє `httpx.MockTransport`.
"""

import datetime as dt
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from conftest import auth_header
from sqlalchemy import select
from test_sync import attempt, batch, content, now, send

from app.models.lessons import Question
from app.models.test_analysis import TestAnalysis
from app.services import test_analysis as service
from app.services.ai import AIClient
from app.workers import test_analysis as worker
from app.workers.celery_app import celery_app

pytestmark = pytest.mark.anyio

AI_URL = "http://ai.test"
AI_KEY = "internal-key"
RIGHT = lambda c: {c.q1.id: ["a"], c.q2.id: ["a", "c"]}  # noqa: E731
WRONG = lambda c: {c.q1.id: ["b"], c.q2.id: ["a"]}  # noqa: E731


def ai_response(body: dict[str, Any]) -> dict[str, Any]:
    """Відповідь у форматі AI-сервісу: по запису на кожен псевдонім із запиту."""
    ids = [s["student_id"] for s in body["students"]]
    return {
        "class_summary": {
            "students_total": len(ids),
            "average_score_pct": 60.0,
            "passed_count": 1,
            "pass_score_pct": body["pass_score_pct"],
            "needs_support_ids": ids[1:],
            "overview": "Клас загалом засвоїв тему.",
            "recommendations": ["Повторити дроби"],
        },
        "skills": [],
        "questions": [
            {
                "question_id": q["id"],
                "position": n,
                "skill": "Дроби",
                "correct_pct": 50.0,
                "correct_count": 1,
                "answered_count": len(ids),
                "status": "ok",
                "wrong_answers": [
                    {"option_ids": ["b"], "option_text": "2", "count": 1, "student_ids": ids[1:]}
                ],
            }
            for n, q in enumerate(body["questions"], start=1)
        ],
        "misconceptions": [],
        "students": [
            {
                "student_id": sid,
                "score_pct": 100.0 if n == 0 else 0.0,
                "passed": n == 0,
                "status": "strong" if n == 0 else "needs_support",
                "correct_question_ids": [q["id"] for q in body["questions"]] if n == 0 else [],
                "wrong_question_ids": [] if n == 0 else [q["id"] for q in body["questions"]],
                "strong_skills": [],
                "weak_skills": [],
                "misconception_ids": [],
                "feedback": {
                    "teacher": f"Вчителю про {sid}",
                    "student": f"Учню {sid}",
                    "parent": f"Батькам {sid}",
                },
            }
            for n, sid in enumerate(ids)
        ],
        "llm_used": True,
    }


class FakeAI:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"code": "invalid_test"})
        return httpx.Response(200, json=ai_response(json.loads(request.content)))

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]

    def client(self) -> AIClient:
        return AIClient(AI_URL, AI_KEY, transport=httpx.MockTransport(self.handler))


@pytest.fixture
def ai(db_session, monkeypatch) -> FakeAI:
    """Задача бачить тестову транзакцію і фейковий AI."""
    fake = FakeAI()

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr(worker, "standalone_session", session)
    monkeypatch.setattr(worker, "ai_client", fake.client)
    return fake


@pytest.fixture
async def c(db_session, factory, world):
    return await content(db_session, factory, world.class_a, world.teacher_a)


@pytest.fixture
async def students(client, factory, world, c):
    """Троє учнів класу з зарахованими спробами: перший — усе правильно."""
    second = await factory.student(world.class_a, "Олена", "Шевчук")
    third = await factory.student(world.class_a, "Петро", "Яковенко")
    at = now() - dt.timedelta(minutes=10)
    for n, (student, answers) in enumerate(
        [(world.student_a, RIGHT(c)), (second, WRONG(c)), (third, WRONG(c))]
    ):
        await send(client, student, batch(attempt(c.test.id, answers, at + dt.timedelta(n))))
    return [world.student_a, second, third]


def url(world, c) -> str:
    return f"/classes/{world.class_a.id}/tests/{c.test.id}/analysis"


async def run_task(analysis_id: str) -> str | None:
    return await worker._run(uuid.UUID(analysis_id))


# ---------- запуск ----------


async def test_not_enough_attempts(client, world, c) -> None:
    await send(client, world.student_a, batch(attempt(c.test.id, RIGHT(c), now())))
    r = await client.post(url(world, c), headers=auth_header(world.teacher_a))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NOT_ENOUGH_ATTEMPTS"
    assert r.json()["error"]["details"] == {"attempts": 1, "required": 3}


async def test_get_before_any_analysis_is_404(client, world, c) -> None:
    r = await client.get(url(world, c), headers=auth_header(world.teacher_a))
    assert r.status_code == 404 and r.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


async def test_full_flow_draft_edit_publish_feedback(
    client, db_session, world, c, students, ai, enqueued
) -> None:
    teacher = auth_header(world.teacher_a)
    r = await client.post(url(world, c), headers=teacher)
    assert r.status_code == 202, r.text
    analysis = r.json()
    assert analysis["status"] == "processing" and analysis["attempts_count"] == 3
    assert analysis["result"] is None
    runs = [x for x in enqueued if x.name == "test_analysis.run"]
    assert [x.args for x in runs] == [[analysis["id"]]]

    # Повторний клік поки йде аналіз — той самий аналіз, нова задача не ставиться.
    again = await client.post(url(world, c), headers=teacher)
    assert again.status_code == 200 and again.json()["id"] == analysis["id"]
    assert len([x for x in enqueued if x.name == "test_analysis.run"]) == 1

    assert await run_task(analysis["id"]) == "draft"

    # В AI — лише псевдоніми, без id та імен учнів.
    (body,) = ai.bodies
    (request,) = ai.requests
    assert request.url.path == "/ai/v1/test-analysis"
    assert request.headers["X-Internal-Key"] == AI_KEY
    raw = request.content.decode()
    for s in students:
        assert str(s.id) not in raw and s.display_name not in raw
    assert [s["student_id"] for s in body["students"]] == ["s1", "s2", "s3"]
    assert body["students"][0]["answers"] == {str(c.q1.id): ["a"], str(c.q2.id): ["a", "c"]}
    assert body["grade"] == 7 and body["subject"] == "Математика"
    assert body["lesson_title"] == "Дроби" and body["pass_score_pct"] == 60.0
    assert [q["id"] for q in body["questions"]] == [str(c.q1.id), str(c.q2.id)]

    r = await client.get(url(world, c), headers=teacher)
    assert r.status_code == 200
    draft = r.json()
    assert draft["status"] == "draft" and draft["completed_at"] is not None
    ids = [str(s.id) for s in students]
    result = draft["result"]
    assert [s["student_id"] for s in result["students"]] == ids
    assert result["class_summary"]["needs_support_ids"] == ids[1:]
    assert result["questions"][0]["wrong_answers"][0]["student_ids"] == ids[1:]
    assert result["students"][1]["feedback"]["student"] == "Учню s2"
    assert all(s["feedback_edited"] is False for s in result["students"])

    # Правка вчителя: лише текст учню; потім повернення тексту AI через null.
    edit = f"/test-analyses/{draft['id']}/students/{ids[1]}"
    r = await client.patch(edit, json={"student": "Молодець, Олено!"}, headers=teacher)
    assert r.status_code == 200, r.text
    assert r.json()["feedback"] == {
        "teacher": "Вчителю про s2",
        "student": "Молодець, Олено!",
        "parent": "Батькам s2",
    }
    assert r.json()["feedback_edited"] is True
    r = await client.patch(edit, json={"parent": "Похваліть Олену"}, headers=teacher)
    assert r.json()["feedback"]["student"] == "Молодець, Олено!"  # відсутнє поле — без змін
    r = await client.patch(edit, json={"student": None}, headers=teacher)
    assert r.json()["feedback"]["student"] == "Учню s2"
    assert r.json()["feedback"]["parent"] == "Похваліть Олену"

    # Поки не опубліковано — учень нічого не бачить.
    feedback_url = f"/students/{ids[1]}/test-feedback"
    r = await client.get(feedback_url, headers=auth_header(students[1]))
    assert r.status_code == 200 and r.json() == {"items": []}

    r = await client.post(f"/test-analyses/{draft['id']}/publish", headers=teacher)
    assert r.status_code == 200 and r.json()["status"] == "published"
    published_at = r.json()["published_at"]
    r = await client.post(f"/test-analyses/{draft['id']}/publish", headers=teacher)
    assert r.status_code == 200 and r.json()["published_at"] == published_at  # ідемпотентно

    r = await client.patch(edit, json={"student": "пізно"}, headers=teacher)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ANALYSIS_NOT_DRAFT"

    r = await client.get(feedback_url, headers=auth_header(students[1]))
    (item,) = r.json()["items"]
    assert item["text"] == "Учню s2" and item["test_id"] == str(c.test.id)
    assert item["test_title"] == "Тест" and item["subject"] == "Математика"
    assert item["score_pct"] == 0.0 and item["correct_count"] == 0
    assert item["questions_total"] == 2

    r = await client.get(f"/students/{ids[0]}/test-feedback", headers=auth_header(world.parent_a))
    (item,) = r.json()["items"]
    assert item["text"] == "Батькам s1" and item["correct_count"] == 2


async def test_ai_unavailable_marks_failed_and_restart_creates_new(
    client, db_session, world, c, students, ai, monkeypatch
) -> None:
    monkeypatch.setattr(worker, "ai_client", lambda: AIClient("", ""))
    teacher = auth_header(world.teacher_a)
    first = (await client.post(url(world, c), headers=teacher)).json()
    assert await run_task(first["id"]) == "failed"
    r = await client.get(url(world, c), headers=teacher)
    assert r.json()["status"] == "failed"
    assert r.json()["error"] == {"code": "AI_UNAVAILABLE"} and r.json()["result"] is None

    r = await client.post(f"/test-analyses/{first['id']}/publish", headers=teacher)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ANALYSIS_NOT_READY"

    second = await client.post(url(world, c), headers=teacher)
    assert second.status_code == 202 and second.json()["id"] != first["id"]


async def test_ai_422_marks_failed_bad_request(client, world, c, students, ai) -> None:
    ai.status = 422
    analysis = (await client.post(url(world, c), headers=auth_header(world.teacher_a))).json()
    assert await run_task(analysis["id"]) == "failed"
    r = await client.get(url(world, c), headers=auth_header(world.teacher_a))
    assert r.json()["error"] == {"code": "AI_BAD_REQUEST"}


async def test_stale_processing_becomes_failed(client, db_session, world, c, students) -> None:
    analysis = (await client.post(url(world, c), headers=auth_header(world.teacher_a))).json()
    row = await db_session.get(TestAnalysis, uuid.UUID(analysis["id"]))
    row.created_at = now() - dt.timedelta(minutes=10)
    await db_session.flush()
    r = await client.get(url(world, c), headers=auth_header(world.teacher_a))
    assert r.json()["status"] == "failed" and r.json()["error"] == {"code": "AI_TIMEOUT"}
    # Задача, що прокинулась пізніше, вже нічого не змінює.
    assert await service.run(db_session, row.id, AIClient("", ""), None) is None  # type: ignore[arg-type]


async def test_text_and_match_questions_are_not_sent(
    client, db_session, world, c, students, ai
) -> None:
    db_session.add_all(
        [
            Question(
                test_id=c.test.id,
                position=3,
                kind="text",
                prompt="Скільки?",
                options=[],
                answer_key=["2"],
            ),
            Question(
                test_id=c.test.id,
                position=4,
                kind="match",
                prompt="Пари",
                options=[{"id": "a", "text": "1"}],
                right_options=[{"id": "x", "text": "один"}],
                answer_key={"a": "x"},
            ),
        ]
    )
    await db_session.flush()
    analysis = (await client.post(url(world, c), headers=auth_header(world.teacher_a))).json()
    await run_task(analysis["id"])
    assert [q["kind"] for q in ai.bodies[0]["questions"]] == ["single", "multiple"]


def test_restore_ids_drops_unknown_pseudonyms() -> None:
    mapping = {"s1": "id-1", "s2": "id-2"}
    raw = {
        "class_summary": {"needs_support_ids": ["s2", "s9"]},
        "students": [{"student_id": "s1"}, {"student_id": "s9"}],
        "misconceptions": [{"student_ids": ["s1", "s2"]}],
    }
    assert service.restore_ids(raw, mapping) == {
        "class_summary": {"needs_support_ids": ["id-2"]},
        "students": [{"student_id": "id-1"}],
        "misconceptions": [{"student_ids": ["id-1", "id-2"]}],
    }


# ---------- права доступу ----------


async def test_only_teacher_of_the_class(client, db_session, factory, world, c, students) -> None:
    for user in (world.teacher_b, world.admin, world.student_a, world.parent_a):
        r = await client.post(url(world, c), headers=auth_header(user))
        assert r.status_code == 403, user.role
        r = await client.get(url(world, c), headers=auth_header(user))
        assert r.status_code == 403, user.role

    # Тест уроку іншого класу через свій клас — 404.
    other = await content(db_session, factory, world.class_b, world.teacher_b)
    r = await client.post(
        f"/classes/{world.class_a.id}/tests/{other.test.id}/analysis",
        headers=auth_header(world.teacher_a),
    )
    assert r.status_code == 404

    analysis = (await client.post(url(world, c), headers=auth_header(world.teacher_a))).json()
    for path in (f"/test-analyses/{analysis['id']}/publish",):
        r = await client.post(path, headers=auth_header(world.teacher_b))
        assert r.status_code == 403
    r = await client.post(
        f"/test-analyses/{uuid.uuid4()}/publish", headers=auth_header(world.teacher_a)
    )
    assert r.status_code == 404


async def test_feedback_access(client, world, students) -> None:
    sid = world.student_a.id
    assert (
        await client.get(f"/students/{sid}/test-feedback", headers=auth_header(world.student_a))
    ).status_code == 200
    for user in (world.teacher_a, world.admin, world.parent_free, students[1]):
        r = await client.get(f"/students/{sid}/test-feedback", headers=auth_header(user))
        assert r.status_code == 403, user.role


async def test_forget_student_removes_them_from_results(
    client, db_session, world, c, students, ai
) -> None:
    analysis = (await client.post(url(world, c), headers=auth_header(world.teacher_a))).json()
    await run_task(analysis["id"])
    gone = str(students[1].id)
    assert await service.forget_student(db_session, students[1].id) == 1
    await db_session.flush()
    row = await db_session.scalar(select(TestAnalysis))
    assert gone not in json.dumps(row.result)
    assert len(row.result["students"]) == 2


def test_task_is_registered() -> None:
    assert "test_analysis.run" in celery_app.tasks
