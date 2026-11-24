"""Редактор уроку: порядок модулів/карток/питань, копія уроку, нові типи питань (`text`,
`match`), пояснення до питань, медіа карток, розмір і ліміт, локатори проблем публікації."""

import uuid

import anyio
import pytest
from alembic import command
from alembic.config import Config
from conftest import BACKEND_DIR, auth_header
from httpx import AsyncClient
from sqlalchemy import func, select, text
from test_lessons import QUESTION, add_card, add_module, create_lesson
from test_media import MP4, PNG, VTT, stored_files, upload
from test_packs import course  # noqa: F401 — фікстура
from test_sync import attempt, batch, content, now, send

from app.core.config import get_settings
from app.models.lessons import Lesson, MediaAsset, Question, Test
from app.models.sync import Attempt
from app.services import packs as packs_service
from app.services import sync as sync_service
from app.services.grading import is_correct, normalize_text

pytestmark = pytest.mark.anyio


def _id() -> str:
    return str(uuid.uuid4())


async def add_test(client: AsyncClient, teacher, lesson_id: str, window: bool = False) -> dict:
    body = {"id": _id(), "title": "Перевір себе", "window_enabled": window}
    if window:
        body["window_hours"] = 48
    resp = await client.post(f"/lessons/{lesson_id}/tests", json=body, headers=auth_header(teacher))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_question(client: AsyncClient, teacher, test_id: str, **kw):
    return await client.post(
        f"/tests/{test_id}/questions",
        json={**QUESTION, "id": _id(), **kw},
        headers=auth_header(teacher),
    )


TEXT_Q = {
    "kind": "text",
    "prompt": "Як називається число над рискою дробу?",
    "options": [],
    "answer_key": ["чисельник", "верхнє число"],
}
MATCH_Q = {
    "kind": "match",
    "prompt": "Зістав дріб і десятковий запис",
    "options": [{"id": "l1", "text": "1/2"}, {"id": "l2", "text": "1/4"}],
    "right_options": [
        {"id": "r1", "text": "0,25"},
        {"id": "r2", "text": "0,5"},
        {"id": "r3", "text": "0,75"},
    ],
    "answer_key": {"l1": "r2", "l2": "r1"},
}


@pytest.fixture
async def draft(client: AsyncClient, world, factory):
    subject = await factory.subject()
    return await create_lesson(client, world.teacher_a, subject)


# ---------- порядок ----------


async def test_reorder_modules(client: AsyncClient, world, factory, draft) -> None:
    lid = draft["id"]
    h = auth_header(world.teacher_a)
    shelter = [(await add_module(client, world.teacher_a, lid, p)).json() for p in (1, 2, 3)]
    main = (await add_module(client, world.teacher_a, lid, 1, part="main")).json()
    await add_card(client, world.teacher_a, shelter[2]["id"])
    order = [shelter[2]["id"], shelter[0]["id"], shelter[1]["id"]]
    url = f"/lessons/{lid}/modules/order"

    resp = await client.put(url, json={"part": "shelter", "ids": order}, headers=h)
    assert resp.status_code == 200, resp.text
    assert [m["id"] for m in resp.json()] == order
    assert [m["position"] for m in resp.json()] == [1, 2, 3]
    assert len(resp.json()[0]["cards"]) == 1  # модулі з картками
    # Повтор того самого порядку — той самий результат.
    again = await client.put(url, json={"part": "shelter", "ids": order}, headers=h)
    assert again.status_code == 200 and again.json() == resp.json()
    lesson = (await client.get(f"/lessons/{lid}", headers=h)).json()
    assert [m["id"] for m in lesson["modules"]] == [*order, main["id"]]
    # Нову позицію після перенумерації можна зайняти.
    assert (await add_module(client, world.teacher_a, lid, 4)).status_code == 201

    # Набір має збігатися з поточним.
    full = [m["id"] for m in (await client.get(f"/lessons/{lid}", headers=h)).json()["modules"]]
    shelter_ids = full[:4]
    bad = await client.put(url, json={"part": "shelter", "ids": shelter_ids[:3]}, headers=h)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "ORDER_MISMATCH"
    assert bad.json()["error"]["details"]["missing"] == [shelter_ids[3]]
    bad = await client.put(
        url, json={"part": "shelter", "ids": [*shelter_ids, main["id"]]}, headers=h
    )
    assert bad.json()["error"]["details"]["unknown"] == [main["id"]]
    bad = await client.put(
        url, json={"part": "shelter", "ids": [*shelter_ids, shelter_ids[0]]}, headers=h
    )
    assert bad.json()["error"]["details"]["duplicates"] == [shelter_ids[0]]
    assert (
        await client.put(url, json={"part": "main", "ids": [main["id"]]}, headers=h)
    ).status_code == 200
    assert (await client.put(url, json={"part": "other", "ids": []}, headers=h)).status_code == 422

    # Права: лише автор-вчитель.
    body = {"part": "main", "ids": [main["id"]]}
    assert (
        await client.put(url, json=body, headers=auth_header(world.teacher_b))
    ).status_code == 403
    for user in (world.admin, world.student_a, world.parent_a):
        assert (await client.put(url, json=body, headers=auth_header(user))).status_code == 403
    assert (
        await client.put(f"/lessons/{uuid.uuid4()}/modules/order", json=body, headers=h)
    ).status_code == 404

    # Опублікований урок незмінний.
    assert (await client.post(f"/lessons/{lid}/publish", headers=h)).status_code == 200
    locked = await client.put(url, json=body, headers=h)
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "LESSON_PUBLISHED"


async def test_reorder_cards_and_questions(client: AsyncClient, world, draft) -> None:
    lid = draft["id"]
    h = auth_header(world.teacher_a)
    module = (await add_module(client, world.teacher_a, lid)).json()
    c1 = (await add_card(client, world.teacher_a, module["id"], position=1)).json()
    c2 = (await add_card(client, world.teacher_a, module["id"], position=7)).json()
    url = f"/modules/{module['id']}/cards/order"
    resp = await client.put(url, json={"ids": [c2["id"], c1["id"]]}, headers=h)
    assert resp.status_code == 200, resp.text
    assert [(c["id"], c["position"]) for c in resp.json()] == [(c2["id"], 1), (c1["id"], 2)]
    bad = await client.put(url, json={"ids": [c2["id"]]}, headers=h)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "ORDER_MISMATCH"
    assert (
        await client.put(
            url, json={"ids": [c1["id"], c2["id"]]}, headers=auth_header(world.teacher_b)
        )
    ).status_code == 403
    assert (
        await client.put(
            url, json={"ids": [c1["id"], c2["id"]]}, headers=auth_header(world.student_a)
        )
    ).status_code == 403
    assert (
        await client.put(f"/modules/{uuid.uuid4()}/cards/order", json={"ids": []}, headers=h)
    ).status_code == 404

    test = await add_test(client, world.teacher_a, lid)
    q1 = (await add_question(client, world.teacher_a, test["id"], position=1)).json()
    q2 = (await add_question(client, world.teacher_a, test["id"], position=2)).json()
    q3 = (await add_question(client, world.teacher_a, test["id"], position=3)).json()
    url = f"/tests/{test['id']}/questions/order"
    order = [q3["id"], q1["id"], q2["id"]]
    resp = await client.put(url, json={"ids": order}, headers=h)
    assert resp.status_code == 200, resp.text
    assert [q["id"] for q in resp.json()] == order
    assert [q["position"] for q in resp.json()] == [1, 2, 3]
    assert (
        await client.put(url, json={"ids": [q1["id"], q2["id"], str(uuid.uuid4())]}, headers=h)
    ).json()["error"]["details"]["unknown"]
    assert (
        await client.put(url, json={"ids": order}, headers=auth_header(world.teacher_b))
    ).status_code == 403
    lesson = (await client.get(f"/lessons/{lid}", headers=h)).json()
    assert [q["id"] for q in lesson["tests"][0]["questions"]] == order


# ---------- нові типи питань і пояснення ----------


async def test_question_kinds_validation_and_explanation(client: AsyncClient, world, draft) -> None:
    test = await add_test(client, world.teacher_a, draft["id"])
    tid = test["id"]
    h = auth_header(world.teacher_a)

    single = await add_question(client, world.teacher_a, tid, explanation="  Бо 2/4 + 1/4.  ")
    assert single.status_code == 201, single.text
    assert single.json()["explanation"] == "Бо 2/4 + 1/4."
    assert single.json()["right_options"] is None
    txt = await add_question(client, world.teacher_a, tid, position=2, **TEXT_Q)
    assert txt.status_code == 201, txt.text
    assert txt.json()["options"] == [] and txt.json()["answer_key"] == TEXT_Q["answer_key"]
    match = await add_question(client, world.teacher_a, tid, position=3, **MATCH_Q)
    assert match.status_code == 201, match.text
    assert match.json()["answer_key"] == MATCH_Q["answer_key"]
    assert match.json()["right_options"] == MATCH_Q["right_options"]
    # Повтор — той самий ресурс.
    again = await client.post(
        f"/tests/{tid}/questions",
        json={**QUESTION, **MATCH_Q, "id": match.json()["id"], "position": 3},
        headers=h,
    )
    assert again.status_code == 200

    bad_cases = [
        {**TEXT_Q, "options": [{"id": "a", "text": "x"}]},
        {**TEXT_Q, "answer_key": []},
        {**TEXT_Q, "answer_key": ["   "]},
        {**TEXT_Q, "answer_key": ["x"] * 21},
        {**TEXT_Q, "answer_key": {"a": "b"}},
        {**MATCH_Q, "right_options": None},
        {**MATCH_Q, "answer_key": ["l1"]},
        {**MATCH_Q, "answer_key": {"l1": "r2"}},
        {**MATCH_Q, "answer_key": {"l1": "r2", "l2": "r2"}},
        {**MATCH_Q, "answer_key": {"l1": "r2", "l2": "zz"}},
        {**MATCH_Q, "right_options": [{"id": "r1", "text": "a"}, {"id": "r1", "text": "b"}]},
        {"right_options": MATCH_Q["right_options"]},  # праві елементи лише в match
        {"kind": "multiple", "options": [{"id": "a", "text": "x"}]},
        {"explanation": "x" * 2001},
    ]
    for i, case in enumerate(bad_cases, start=10):
        resp = await add_question(client, world.teacher_a, tid, position=i, **case)
        assert resp.status_code == 422, (case, resp.text)

    # match → single: праві елементи прибираються самі.
    qid = match.json()["id"]
    changed = await client.patch(
        f"/questions/{qid}", json={"kind": "single", "answer_key": ["l1"]}, headers=h
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["right_options"] is None and changed.json()["kind"] == "single"
    # single → match без правих елементів — помилка.
    assert (
        await client.patch(
            f"/questions/{qid}", json={"kind": "match", "answer_key": {"l1": "r1"}}, headers=h
        )
    ).status_code == 422
    # Пояснення прибирається null-ом.
    sid = single.json()["id"]
    cleared = await client.patch(f"/questions/{sid}", json={"explanation": None}, headers=h)
    assert cleared.status_code == 200 and cleared.json()["explanation"] is None
    updated = await client.patch(f"/questions/{sid}", json={"explanation": "Нове"}, headers=h)
    assert updated.json()["explanation"] == "Нове"
    assert (
        await client.patch(f"/questions/{sid}", json={"kind": None}, headers=h)
    ).status_code == 422
    assert (
        await client.patch(
            f"/questions/{sid}", json={"explanation": "x"}, headers=auth_header(world.teacher_b)
        )
    ).status_code == 403


def test_normalize_text() -> None:
    assert normalize_text("  Пам’ять   і  ЗНАННЯ ") == "пам'ять і знання"
    for variant in ("пам'ять", "пам’ять", "памʼять", "пам`ять", "пам‘ять"):
        assert normalize_text(variant) == "пам'ять"
    assert normalize_text("\tчисельник\n") == "чисельник"
    assert normalize_text("   ") == ""


@pytest.mark.parametrize(
    ("kind", "key", "answer", "ok"),
    [
        ("single", ["a"], ["a"], True),
        ("single", ["a"], ["b"], False),
        ("multiple", ["a", "c"], ["c", "a"], True),
        ("multiple", ["a", "c"], ["a"], False),
        ("multiple", ["a"], None, False),
        ("multiple", ["a"], {"a": "b"}, False),
        ("text", ["чисельник"], ["  ЧИСЕЛЬНИК "], True),
        ("text", ["Пам'ять"], ["памʼять"], True),
        ("text", ["дві  частини"], ["дві частини"], True),
        ("text", ["чисельник"], ["знаменник"], False),
        ("text", ["чисельник"], ["чисельник", "знаменник"], False),
        ("text", ["чисельник"], [""], False),
        ("text", ["чисельник"], {"a": "b"}, False),
        ("match", {"l1": "r2", "l2": "r1"}, {"l2": "r1", "l1": "r2"}, True),
        ("match", {"l1": "r2", "l2": "r1"}, {"l1": "r2"}, False),
        ("match", {"l1": "r2", "l2": "r1"}, {"l1": "r2", "l2": "r3"}, False),
        ("match", {"l1": "r2"}, ["r2"], False),
        ("single", [], [], False),
    ],
)
def test_is_correct(kind, key, answer, ok) -> None:
    assert is_correct(kind, key, answer) is ok


async def test_server_grades_new_kinds(client: AsyncClient, db_session, factory, world) -> None:
    c = await content(db_session, factory, world.class_a, world.teacher_a)
    db_session.add_all(
        [
            Question(
                test_id=c.test.id,
                position=3,
                kind="text",
                prompt="Над рискою?",
                options=[],
                answer_key=["чисельник", "пам'ять"],
                points=2,
            ),
            Question(
                test_id=c.test.id,
                position=4,
                kind="match",
                prompt="Зістав",
                options=MATCH_Q["options"],
                right_options=MATCH_Q["right_options"],
                answer_key=MATCH_Q["answer_key"],
                points=4,
            ),
        ]
    )
    await db_session.flush()
    qs = {
        q.kind: q
        for q in await db_session.scalars(select(Question).where(Question.test_id == c.test.id))
    }

    async def score(answers: dict) -> float:
        event = attempt(c.test.id, answers, now())
        results = await send(client, world.student_a, batch(event))
        assert results[0]["status"] == "accepted", results
        row = await db_session.scalar(
            select(Attempt).where(Attempt.client_event_id == uuid.UUID(event["client_event_id"]))
        )
        return float(row.score)

    # Бали: single 1, multiple 3, text 2, match 4 = 10.
    full = {
        qs["single"].id: ["a"],
        qs["multiple"].id: ["c", "a"],
        qs["text"].id: ["  ПАМ’ЯТЬ "],
        qs["match"].id: {"l1": "r2", "l2": "r1"},
    }
    assert await score(full) == 100.0
    # Неповна відповідність — 0 за питання (часткових балів немає).
    assert await score({**full, qs["match"].id: {"l1": "r2", "l2": "r3"}}) == 60.0
    assert await score({**full, qs["text"].id: ["знаменник"]}) == 80.0
    # Відповідь не того формату — неправильна, а не відхилена подія.
    assert await score({**full, qs["match"].id: ["r2", "r1"]}) == 60.0
    # Старий формат лишається.
    assert await score({qs["single"].id: ["a"]}) == 10.0

    # Задовгий текст відповіді — invalid_payload.
    long = attempt(c.test.id, {qs["text"].id: ["x" * 201]}, now())
    results = await send(client, world.student_a, batch(long))
    assert (results[0]["status"], results[0]["reason"]) == ("rejected", "invalid_payload")

    # Вчитель додав прийнятну відповідь — переоцінка зараховує текст.
    qs["text"].answer_key = ["чисельник", "пам'ять", "знаменник"]
    await db_session.flush()
    await sync_service.regrade_test(db_session, c.test.id)
    scores = sorted(
        float(s)
        for s in await db_session.scalars(select(Attempt.score).where(Attempt.test_id == c.test.id))
    )
    assert scores.count(100.0) == 2


# ---------- пакет ----------


async def test_pack_has_key_and_explanation_only_for_training(
    db_session,
    world,
    course,  # noqa: F811
) -> None:
    db = db_session
    course.question.explanation = "Зведи до спільного знаменника."
    db.add_all(
        [
            Question(test_id=course.test.id, position=2, **{**TEXT_Q, "explanation": "Над рискою"}),
            Question(test_id=course.test.id, position=3, **MATCH_Q),
        ]
    )
    graded = Test(
        lesson_id=course.lesson.id, title="Контрольна", window_enabled=True, window_hours=48
    )
    db.add(graded)
    await db.flush()
    db.add_all(
        [
            Question(test_id=graded.id, position=1, **{**MATCH_Q, "explanation": "Секрет"}),
            Question(test_id=graded.id, position=2, **{**TEXT_Q, "explanation": "Секрет"}),
        ]
    )
    await db.flush()
    body, _, _ = await packs_service.build_content(db, world.class_a, course.day)
    tests = {t["id"]: t for t in body["lessons"][0]["tests"]}

    practice = tests[str(course.test.id)]["questions"]
    assert practice[0]["explanation"] == "Зведи до спільного знаменника."
    assert practice[1]["kind"] == "text" and practice[1]["answer_key"] == TEXT_Q["answer_key"]
    assert practice[1]["explanation"] == "Над рискою" and practice[1]["options"] == []
    assert practice[2]["answer_key"] == MATCH_Q["answer_key"]
    assert practice[2]["right_options"] == MATCH_Q["right_options"]
    assert "explanation" not in practice[2]

    window = tests[str(graded.id)]["questions"]
    for q in window:
        assert "answer_key" not in q and "explanation" not in q
    assert window[0]["right_options"] == MATCH_Q["right_options"]
    assert "Секрет".encode() not in packs_service.canonical_json(tests[str(graded.id)])


async def test_pack_keeps_old_question_format(db_session, world, course) -> None:  # noqa: F811
    """Питання старих типів без пояснення — той самий JSON, що й до нових полів: хеш пакетів,
    зібраних раніше, не змінюється, нових версій не з'являється."""
    body, _, _ = await packs_service.build_content(db_session, world.class_a, course.day)
    question = body["lessons"][0]["tests"][0]["questions"][0]
    assert set(question) == {"id", "position", "kind", "prompt", "options", "points", "answer_key"}
    card = body["lessons"][0]["modules"][0]["cards"][0]
    assert "media" not in card


# ---------- копія уроку ----------


async def _rich_lesson(client: AsyncClient, world, factory) -> dict:
    """Урок teacher_a: модуль з текстовою, зображенням і відео (із субтитрами) картками,
    тест із питанням і поясненням."""
    subject = await factory.subject()
    lesson = await create_lesson(client, world.teacher_a, subject)
    lid = lesson["id"]
    h = auth_header(world.teacher_a)
    m1 = (await add_module(client, world.teacher_a, lid, 1)).json()
    m2 = (await add_module(client, world.teacher_a, lid, 2, part="main")).json()
    await add_card(client, world.teacher_a, m1["id"], position=1)
    image = (await upload(client, world.teacher_a, "image", "image/png", PNG)).json()
    video = (await upload(client, world.teacher_a, "video", "video/mp4", MP4)).json()
    vtt = (await upload(client, world.teacher_a, "subtitles", "text/vtt", VTT)).json()
    await client.patch(f"/media/{video['id']}", json={"subtitles_id": vtt["id"]}, headers=h)
    await add_card(client, world.teacher_a, m1["id"], "image", image["id"], position=2)
    await add_card(client, world.teacher_a, m2["id"], "video", video["id"], position=1)
    test = await add_test(client, world.teacher_a, lid)
    await add_question(client, world.teacher_a, test["id"], explanation="Розбір")
    await add_question(client, world.teacher_a, test["id"], position=2, **MATCH_Q)
    return (await client.get(f"/lessons/{lid}", headers=h)).json()


def _shape(lesson: dict) -> list:
    """Вміст уроку без id, автора й часу — для порівняння копії з джерелом."""
    return [
        lesson["title"],
        lesson["shelter_part"],
        lesson["main_part"],
        lesson["grade"],
        [
            (
                m["part"],
                m["position"],
                m["title"],
                [(c["kind"], c["position"], c["body"]) for c in m["cards"]],
            )
            for m in lesson["modules"]
        ],
        [
            (
                t["title"],
                t["window_enabled"],
                [
                    {k: v for k, v in q.items() if k not in ("id", "test_id")}
                    for q in t["questions"]
                ],
            )
            for t in lesson["tests"]
        ],
    ]


async def test_copy_colleague_lesson(
    client: AsyncClient, db_session, world, factory, media_storage
) -> None:
    source = await _rich_lesson(client, world, factory)
    files = len(stored_files(media_storage))
    copy_id = _id()
    hb = auth_header(world.teacher_b)
    resp = await client.post(f"/lessons/{source['id']}/copy", json={"id": copy_id}, headers=hb)
    assert resp.status_code == 201, resp.text
    copy = resp.json()
    assert copy["id"] == copy_id and copy["author_id"] == str(world.teacher_b.id)
    assert copy["status"] == "draft" and copy["version"] == 1
    assert copy["copied_from_id"] == source["id"]
    assert _shape(copy) == _shape(source)
    source_ids = {m["id"] for m in source["modules"]} | {t["id"] for t in source["tests"]}
    assert not source_ids & ({m["id"] for m in copy["modules"]} | {t["id"] for t in copy["tests"]})

    # Медіа колеги — нові записи вчителя на ті самі файли; файли не дублюються.
    src_video = source["modules"][1]["cards"][0]["media"]
    new_video = copy["modules"][1]["cards"][0]["media"]
    assert new_video["id"] != src_video["id"] and new_video["url"] == src_video["url"]
    assert new_video["subtitles"]["url"] == src_video["subtitles"]["url"]
    assert new_video["subtitles"]["id"] != src_video["subtitles"]["id"]
    owners = set(
        await db_session.scalars(
            select(MediaAsset.uploaded_by).where(
                MediaAsset.id.in_(
                    [uuid.UUID(new_video["id"]), uuid.UUID(new_video["subtitles_id"])]
                )
            )
        )
    )
    assert owners == {world.teacher_b.id}
    assert len(stored_files(media_storage)) == files
    assert copy["size_bytes"] == source["size_bytes"]
    # Власне медіа копії вчитель може змінювати (субтитри), а копію — опублікувати.
    assert (
        await client.patch(f"/media/{new_video['id']}", json={"subtitles_id": None}, headers=hb)
    ).status_code == 200
    assert (
        await client.patch(
            f"/media/{new_video['id']}",
            json={"subtitles_id": new_video["subtitles_id"]},
            headers=hb,
        )
    ).status_code == 200
    assert (await client.post(f"/lessons/{copy_id}/publish", headers=hb)).status_code == 200
    # Джерело не змінилося.
    ha = auth_header(world.teacher_a)
    assert (await client.get(f"/lessons/{source['id']}", headers=ha)).json() == source

    # Повтор — та сама копія (навіть з іншою назвою), нічого не дублюється.
    again = await client.post(
        f"/lessons/{source['id']}/copy", json={"id": copy_id, "title": "Інша"}, headers=hb
    )
    assert again.status_code == 200 and again.json()["id"] == copy_id
    assert again.json()["title"] == source["title"]
    count = await db_session.scalar(
        select(func.count())
        .select_from(Lesson)
        .where(Lesson.copied_from_id == uuid.UUID(source["id"]))
    )
    assert count == 1
    # Той самий id: інше джерело чи інший вчитель — конфлікт.
    other = await create_lesson(client, world.teacher_b, await factory.subject())
    conflict = await client.post(f"/lessons/{other['id']}/copy", json={"id": copy_id}, headers=hb)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "ID_CONFLICT"
    assert (
        await client.post(f"/lessons/{source['id']}/copy", json={"id": copy_id}, headers=ha)
    ).status_code == 409
    # Id наявного уроку (не копії) — конфлікт.
    assert (
        await client.post(f"/lessons/{source['id']}/copy", json={"id": other["id"]}, headers=hb)
    ).status_code == 409


async def test_copy_own_lesson_reuses_media_and_title(
    client: AsyncClient, world, factory, media_storage
) -> None:
    source = await _rich_lesson(client, world, factory)
    h = auth_header(world.teacher_a)
    resp = await client.post(
        f"/lessons/{source['id']}/copy", json={"id": _id(), "title": "  Дроби (7-Б) "}, headers=h
    )
    assert resp.status_code == 201, resp.text
    copy = resp.json()
    assert copy["title"] == "Дроби (7-Б)"
    src_media = [c["media_asset_id"] for m in source["modules"] for c in m["cards"]]
    assert [c["media_asset_id"] for m in copy["modules"] for c in m["cards"]] == src_media
    # Копію копії теж можна зробити; правки копії не чіпають джерело.
    module_id = copy["modules"][0]["id"]
    assert (
        await client.patch(f"/modules/{module_id}", json={"title": "Нове"}, headers=h)
    ).status_code == 200
    assert (await client.get(f"/lessons/{source['id']}", headers=h)).json()["modules"][0][
        "title"
    ] == "Модуль"


async def test_copy_access(client: AsyncClient, world, factory, media_storage) -> None:
    source = await _rich_lesson(client, world, factory)
    url = f"/lessons/{source['id']}/copy"
    other_teacher = await factory.teacher(world.other_school)
    for user in (other_teacher, world.admin, world.other_admin, world.student_a, world.parent_a):
        resp = await client.post(url, json={"id": _id()}, headers=auth_header(user))
        assert resp.status_code == 403, user.role
    assert (
        await client.post(
            f"/lessons/{uuid.uuid4()}/copy",
            json={"id": _id()},
            headers=auth_header(world.teacher_a),
        )
    ).status_code == 404
    assert (
        await client.post(
            url, json={"id": _id(), "title": ""}, headers=auth_header(world.teacher_a)
        )
    ).status_code == 422
    assert (await client.post(url, json={"id": _id()})).status_code == 401


# ---------- медіа карток, розмір, проблеми публікації ----------


async def test_lesson_out_media_size_and_limit(
    client: AsyncClient, world, factory, media_storage
) -> None:
    lesson = await _rich_lesson(client, world, factory)
    assert lesson["limit_bytes"] == get_settings().pack_max_day_bytes
    assert lesson["copied_from_id"] is None
    cards = [c for m in lesson["modules"] for c in m["cards"]]
    assert "media" not in cards[0]  # текстова картка
    image = cards[1]["media"]
    assert image["kind"] == "image" and image["url"].startswith("/media/")
    assert image["mime_type"] and image["size_bytes"] > 0 and image["subtitles"] is None
    video = cards[2]["media"]
    assert video["subtitles"]["kind"] == "subtitles" and video["subtitles_id"]
    assert lesson["size_bytes"] >= image["size_bytes"] + video["size_bytes"]

    # Відповіді створення й зміни картки теж несуть медіа.
    h = auth_header(world.teacher_a)
    patched = await client.patch(
        f"/cards/{cards[1]['id']}", json={"body": {"caption": "Пиріг"}}, headers=h
    )
    assert patched.status_code == 200 and patched.json()["media"]["id"] == image["id"]

    # Пояснення рахується в розмір уроку.
    question = lesson["tests"][0]["questions"][0]
    before = (await client.get(f"/lessons/{lesson['id']}", headers=h)).json()["size_bytes"]
    await client.patch(f"/questions/{question['id']}", json={"explanation": "x" * 1000}, headers=h)
    after = (await client.get(f"/lessons/{lesson['id']}", headers=h)).json()["size_bytes"]
    assert after - before == 1000 - len("Розбір".encode())


async def test_publish_problem_has_module_locator(
    client: AsyncClient, world, draft, media_storage
) -> None:
    h = auth_header(world.teacher_a)
    module = (await add_module(client, world.teacher_a, draft["id"])).json()
    video = (await upload(client, world.teacher_a, "video", "video/mp4", MP4)).json()
    card = (await add_card(client, world.teacher_a, module["id"], "video", video["id"])).json()
    test = await add_test(client, world.teacher_a, draft["id"])
    failed = await client.post(f"/lessons/{draft['id']}/publish", headers=h)
    details = {d["check"]: d for d in failed.json()["error"]["details"]}
    assert "video_subtitles" not in details
    assert details["test_questions"]["test_id"] == test["id"]
    lesson = (await client.get(f"/lessons/{draft['id']}", headers=h)).json()
    warnings = {w["check"]: w for w in lesson["warnings"]}
    assert warnings["video_subtitles"]["module_id"] == module["id"]
    assert warnings["video_subtitles"]["card_id"] == card["id"]
    assert warnings["video_subtitles"]["media_asset_id"] == video["id"]


# ---------- міграція ----------


async def test_migration_down_and_up(committed) -> None:
    """Вниз: питання `text`/`match` видаляються (стара схема їх не описує), решта лишається;
    вгору — знову працює."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    f = committed.factory
    school = await f.school()
    teacher = await f.teacher(school)
    subject = await f.subject()
    db = committed.session
    source = Lesson(
        subject_id=subject.id, author_id=teacher.id, title="Т", shelter_part="У", main_part="О"
    )
    db.add(source)
    await db.flush()
    copy = Lesson(
        subject_id=subject.id,
        author_id=teacher.id,
        title="К",
        shelter_part="У",
        main_part="О",
        copied_from_id=source.id,
    )
    test = Test(lesson_id=source.id, title="Т")
    db.add_all([copy, test])
    await db.flush()
    db.add_all(
        [
            Question(test_id=test.id, **{**QUESTION, "explanation": "Р"}),
            Question(test_id=test.id, position=2, **TEXT_Q),
            Question(test_id=test.id, position=3, **MATCH_Q),
        ]
    )
    await db.commit()

    await anyio.to_thread.run_sync(command.downgrade, config, "430365394792")
    try:
        async with committed.maker() as s:
            kinds = list(await s.scalars(text("SELECT kind FROM question ORDER BY position")))
            assert kinds == ["single"]
            columns = set(
                await s.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name IN ('question', 'lesson')"
                    )
                )
            )
            assert not columns & {"explanation", "right_options", "copied_from_id"}
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    async with committed.maker() as s:
        q = await s.scalar(select(Question).where(Question.test_id == test.id))
        assert q.explanation is None and q.right_options is None
        s.add(Question(test_id=test.id, position=2, **TEXT_Q))
        await s.commit()


async def test_list_school_scope_shows_published_colleague_lessons(
    client: AsyncClient, db_session, world, factory, media_storage
) -> None:
    source = await _rich_lesson(client, world, factory)
    hb = auth_header(world.teacher_b)
    resp = await client.get("/lessons", params={"scope": "school"}, headers=hb)
    assert resp.status_code == 200 and resp.json() == []  # чернетки колег не видно

    lesson = await db_session.get(Lesson, uuid.UUID(source["id"]))
    lesson.status = "published"
    await db_session.flush()
    resp = await client.get("/lessons", params={"scope": "school"}, headers=hb)
    assert [item["id"] for item in resp.json()] == [source["id"]]
    # Свої уроки в scope=school не дублюються; звичайний список — лише свої.
    own = await client.get(
        "/lessons", params={"scope": "school"}, headers=auth_header(world.teacher_a)
    )
    assert own.json() == []
    mine = await client.get("/lessons", headers=hb)
    assert source["id"] not in {item["id"] for item in mine.json()}
