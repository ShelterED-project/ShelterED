"""Наскрізні сценарії через кілька модулів: головний сценарій MVP, тест із вікном через правки
уроку, видалення учня посеред роботи, життєвий цикл токенів, паралельність, час (DST, зсув
годинника). Задачі Celery виконуються викликом їхніх сервісних функцій."""

import asyncio
import datetime as dt
import uuid
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from conftest import PASSWORD, auth_header, pushes
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.push import PushSubscription
from app.models.rollcall import RollCallSession, RollCallStatus
from app.models.school import User
from app.models.stats import StudentLessonStat, StudentTestStat
from app.models.sync import Attempt, ModuleProgress, SyncEvent
from app.services import alerts as alerts_service
from app.services import packs as packs_service
from app.services import push as push_service
from app.services import stats as stats_service
from app.services import sync as sync_service
from app.services.alert_provider import ActiveAlerts, AlertProvider, ProviderAlert

pytestmark = pytest.mark.anyio

KYIV = ZoneInfo("Europe/Kyiv")
DEVICE_1 = str(uuid.uuid4())
DEVICE_2 = str(uuid.uuid4())


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(t: dt.datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def ev(kind: str, payload: dict[str, Any], at: dt.datetime, device: str = DEVICE_1) -> dict:
    return {
        "client_event_id": str(uuid.uuid4()),
        "type": kind,
        "device_id": device,
        "occurred_at": iso(at),
        "payload": payload,
    }


def batch(*events: dict, sent_at: dt.datetime | None = None) -> dict:
    return {"sent_at": iso(sent_at or now()), "events": list(events)}


class FakeProvider(AlertProvider):
    name = "alerts.in.ua"

    def __init__(self) -> None:
        self.alerts: list[ProviderAlert] = []

    async def active_alerts(self) -> ActiveAlerts:
        return ActiveAlerts(list(self.alerts), complete=True)


async def ok(response, code: int = 200) -> Any:
    assert response.status_code == code, response.text
    return response.json() if response.content else None


async def count(db, model, *where) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*where)) or 0


# ---------- спільна підготовка через API: школа → клас → вчитель → урок → розклад ----------


async def build_school(cm, *, window: bool = False, modules: int = 2) -> SimpleNamespace:
    """Адмін (з CLI) створює клас і вчителя, вчитель — урок із модулями й тестом, публікує й
    ставить у слот на сьогодні (слот на весь день за Києвом). Пакет збирає «задача»."""
    http = cm.client
    w = SimpleNamespace()
    w.school = await cm.factory.school()
    w.admin = await cm.factory.adult("admin", w.school)
    await cm.session.commit()
    admin = auth_header(w.admin)

    w.class_id = str(uuid.uuid4())
    klass = await ok(
        await http.post(
            "/classes",
            json={"id": w.class_id, "name": "5-А", "grade": 5, "academic_year": "2026/2027"},
            headers=admin,
        ),
        201,
    )
    w.join_code = klass["join_code"]
    email = f"{uuid.uuid4().hex[:8]}@school.ua"
    teacher = await ok(
        await http.post(
            "/admin/users",
            json={"email": email, "display_name": "Олена", "role": "teacher", "password": PASSWORD},
            headers=admin,
        ),
        201,
    )
    w.teacher_id = teacher["id"]
    await ok(await http.put(f"/classes/{w.class_id}/teachers/{w.teacher_id}", headers=admin), 204)
    async with cm.maker() as db:
        w.teacher = await db.get(User, uuid.UUID(w.teacher_id))
    t = auth_header(w.teacher)

    subject_id = str(uuid.uuid4())
    await ok(
        await http.post("/subjects", json={"id": subject_id, "name": "Математика"}, headers=admin),
        201,
    )
    w.today = now().astimezone(KYIV).date()
    w.slot_id = str(uuid.uuid4())
    await ok(
        await http.post(
            f"/classes/{w.class_id}/schedule/slots",
            json={
                "id": w.slot_id,
                "subject_id": subject_id,
                "weekday": w.today.isoweekday(),
                "starts_at": "00:00:00",
                "ends_at": "23:59:59",
                "valid_from": str(w.today - dt.timedelta(days=1)),
            },
            headers=admin,
        ),
        201,
    )
    w.lesson_id = str(uuid.uuid4())
    await ok(
        await http.post(
            "/lessons",
            json={
                "id": w.lesson_id,
                "subject_id": subject_id,
                "title": "Дроби",
                "shelter_part": "Повторюємо дроби в укритті",
            },
            headers=t,
        ),
        201,
    )
    w.modules = []
    for i in range(modules):
        mid = str(uuid.uuid4())
        await ok(
            await http.post(
                f"/lessons/{w.lesson_id}/modules",
                json={
                    "id": mid,
                    "part": "shelter",
                    "position": i + 1,
                    "title": f"М{i}",
                    "duration_min": 4,
                },
                headers=t,
            ),
            201,
        )
        w.modules.append(mid)
    w.test_id = str(uuid.uuid4())
    test_body: dict[str, Any] = {"id": w.test_id, "title": "Перевір себе"}
    if window:
        test_body |= {"window_enabled": True, "window_hours": 24}
    await ok(await http.post(f"/lessons/{w.lesson_id}/tests", json=test_body, headers=t), 201)
    w.q1, w.q2 = str(uuid.uuid4()), str(uuid.uuid4())
    for qid, pos, key, points in ((w.q1, 1, ["a"], 1), (w.q2, 2, ["b"], 3)):
        await ok(
            await http.post(
                f"/tests/{w.test_id}/questions",
                json={
                    "id": qid,
                    "position": pos,
                    "kind": "single",
                    "prompt": f"Питання {pos}",
                    "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                    "answer_key": key,
                    "points": points,
                },
                headers=t,
            ),
            201,
        )
    await ok(await http.post(f"/lessons/{w.lesson_id}/publish", headers=t))
    await ok(
        await http.put(
            f"/classes/{w.class_id}/schedule/slots/{w.slot_id}/lessons/{w.today}",
            json={"lesson_id": w.lesson_id},
            headers=t,
        )
    )
    await rebuild_packs(cm, w)
    return w


async def rebuild_packs(cm, w) -> list:
    async with cm.maker() as db:
        return await packs_service.rebuild_class(db, uuid.UUID(w.class_id), get_settings())


async def join(cm, w, name: str = "Іван", last: str = "Петренко", pin: str = "4321") -> dict:
    return await ok(
        await cm.client.post(
            "/auth/student/join",
            json={"join_code": w.join_code, "display_name": name, "last_name": last, "pin": pin},
        )
    )


def bearer(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def recompute(cm, student_id, class_id) -> None:
    async with cm.maker() as db:
        await stats_service.recompute_student_rows(db, uuid.UUID(str(student_id)))
    async with cm.maker() as db:
        await stats_service.recompute_class(db, uuid.UUID(str(class_id)), get_settings())
        await db.commit()


async def all_changes(cm, headers, cursor: str | None = None) -> tuple[list[dict], str]:
    items: list[dict] = []
    while True:
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = await ok(await cm.client.get("/sync/changes", params=params, headers=headers))
        items += page["changes"]
        cursor = page["next_cursor"]
        if not page["has_more"]:
            return items, cursor


# ---------- 1. головний сценарій MVP ----------


async def test_mvp_main_scenario_end_to_end(committed, enqueued) -> None:
    cm, http = committed, committed.client
    w = await build_school(cm)
    t = auth_header(w.teacher)

    # Учень входить кодом класу й PIN, батьки прив'язуються кодом.
    tokens = await join(cm, w)
    student = bearer(tokens)
    me = await ok(await http.get("/auth/me", headers=student))
    student_id = me["id"]
    code = (await ok(await http.post(f"/students/{student_id}/parent-link-codes", headers=t), 201))[
        "code"
    ]
    parent_user = await cm.factory.adult("parent", None)
    await cm.session.commit()
    parent = auth_header(parent_user)
    await ok(await http.post("/parent/link", json={"code": code}, headers=parent))

    # Рюкзак: маніфест і пакет дня з уроком; ключ відповідей у тренувальному тесті є.
    manifest = await ok(
        await http.get("/packs/manifest", params={"class_id": w.class_id}, headers=student)
    )
    today = [p for p in manifest["packs"] if p["pack_date"] == str(w.today)]
    assert len(today) == 1
    pack = await http.get(f"/packs/{today[0]['id']}", headers=student)
    assert pack.status_code == 200
    body = pack.json()
    lesson = next(item for item in body["lessons"] if item["id"] == w.lesson_id)
    assert [m["id"] for m in lesson["modules"]] == w.modules
    etag = pack.headers["ETag"]
    again = await http.get(f"/packs/{today[0]['id']}", headers={**student, "If-None-Match": etag})
    assert again.status_code == 304

    # Тривога з API посеред уроку: перекличка, push із id уроку.
    provider = FakeProvider()
    provider.alerts = [
        ProviderAlert(
            external_id="e2e-1",
            location_type="oblast",
            location_uid="kyiv",
            started_at=now() - dt.timedelta(minutes=1),
        )
    ]
    async with cm.maker() as db:
        result = await alerts_service.poll(db, provider)
    assert result["started"] == 1
    alert_pushes = pushes(enqueued, "alert")
    assert len(alert_pushes) == 1 and alert_pushes[0]["lesson_id"] == w.lesson_id
    active = await ok(await http.get("/alerts/active", headers=student))
    assert len(active["alerts"]) == 1
    own = await ok(await http.get(f"/students/{student_id}/rollcall/current", headers=student))
    session_id = own["session_id"]
    assert session_id and own["status"] == "no_response"

    # Офлайн: «я в укритті», обидва модулі, тест (q1 правильно, q2 ні → 25 %).
    t0 = now() - dt.timedelta(seconds=55)  # уся робота — між початком тривоги й відбоєм
    offline = [
        ev("rollcall_status", {"session_id": session_id, "status": "in_shelter"}, t0),
        ev(
            "module_progress",
            {"module_id": w.modules[0], "progress_pct": 50},
            t0 + dt.timedelta(seconds=10),
        ),
        ev(
            "module_progress",
            {
                "module_id": w.modules[0],
                "progress_pct": 100,
                "completed_at": iso(t0 + dt.timedelta(seconds=20)),
            },
            t0 + dt.timedelta(seconds=20),
        ),
        ev(
            "module_progress",
            {
                "module_id": w.modules[1],
                "progress_pct": 100,
                "completed_at": iso(t0 + dt.timedelta(seconds=30)),
            },
            t0 + dt.timedelta(seconds=30),
        ),
        ev(
            "test_attempt",
            {
                "test_id": w.test_id,
                "answers": {w.q1: ["a"], w.q2: ["a"]},
                "completed_at": iso(t0 + dt.timedelta(seconds=40)),
            },
            t0 + dt.timedelta(seconds=40),
        ),
        ev(
            "rollcall_status",
            {"session_id": session_id, "status": "safe"},
            t0 + dt.timedelta(seconds=50),
        ),
    ]
    # Обрив мережі: сервер обробив першу половину, відповідь не дійшла.
    first = await ok(await http.post("/sync/events", json=batch(*offline[:3]), headers=student))
    assert [r["status"] for r in first["results"]] == ["accepted"] * 3
    # Повтор усього пакета + паралельний дубль із другої вкладки.
    full = batch(*offline)
    r1, r2 = await asyncio.gather(
        http.post("/sync/events", json=full, headers=student),
        http.post("/sync/events", json=full, headers=student),
    )
    res1, res2 = (await ok(r1))["results"], (await ok(r2))["results"]
    for i, (a, b) in enumerate(zip(res1, res2, strict=True)):
        if i < 3:
            assert a["status"] == b["status"] == "duplicate"
        else:
            assert {a["status"], b["status"]} == {"accepted", "duplicate"}
    async with cm.maker() as db:
        assert await count(db, SyncEvent) == 6
        assert await count(db, Attempt) == 1
        assert await count(db, ModuleProgress) == 2
        assert await count(db, RollCallStatus) == 1
    # Батькам — по одному push на зміну статусу (in_shelter, потім safe).
    statuses = [p["status"] for p in pushes(enqueued, "rollcall_status")]
    assert statuses == ["in_shelter", "safe"]

    # Вчитель бачить перекличку, прогрес і статус тесту; батьки — статус і прогрес дитини.
    await recompute(cm, student_id, w.class_id)
    rc = await ok(await http.get(f"/classes/{w.class_id}/rollcall/current", headers=t))
    assert rc["session"]["summary"] == {"safe": 1, "in_shelter": 0, "no_response": 0}
    progress = await ok(await http.get(f"/classes/{w.class_id}/progress", headers=t))
    row = next(lsn for lsn in progress["lessons"] if lsn["lesson_id"] == w.lesson_id)
    assert row["students_total"] == 1 and row["students_completed"] == 1
    assert row["avg_progress_pct"] == 100 and row["tests_scored"] == 1 and row["avg_score"] == 25.0
    tests = await ok(await http.get(f"/classes/{w.class_id}/tests", headers=t))
    result_row = tests["tests"][0]["students"][0]
    assert result_row["status"] == "not_passed" and result_row["score"] == 25.0
    child = await ok(await http.get(f"/students/{student_id}/rollcall/current", headers=parent))
    assert child["status"] == "safe"
    child_progress = await ok(await http.get(f"/students/{student_id}/progress", headers=parent))
    assert child_progress["lessons"][0]["progress_pct"] == 100
    assert child_progress["tests"][0]["score"] == 25.0

    # Відбій: перекличка закрита, push «відбій».
    provider.alerts = []
    async with cm.maker() as db:
        assert (await alerts_service.poll(db, provider))["ended"] == 1
    assert len(pushes(enqueued, "all_clear")) == 1
    assert (await ok(await http.get(f"/classes/{w.class_id}/rollcall/current", headers=t)))[
        "session"
    ] is None
    async with cm.maker() as db:
        closed = await db.get(RollCallSession, uuid.UUID(session_id))
        assert closed.closed_at is not None
    # Дашборд адміністрації: навчання під час тривоги — 2 модулі по 4 хв одного учня.
    async with cm.maker() as db:
        await stats_service.recompute_alert_study(db, w.school.id, get_settings())
        await db.commit()
    study = await ok(await http.get("/alerts/study", headers=auth_header(w.admin)))
    assert [(a["students"], a["study_minutes"]) for a in study["alerts"]] == [(1, 8)]

    # Стрічка змін: рівно три рядки (прогрес двох модулів, спроба, статус), без дублів.
    items, cursor = await all_changes(cm, student)
    kinds = sorted(ch["kind"] for ch in items)
    assert kinds == ["attempt_result", "module_progress", "module_progress", "rollcall_status"]
    by_kind = {ch["kind"]: ch for ch in items}
    assert by_kind["rollcall_status"]["status"] == "safe"
    assert by_kind["attempt_result"]["credit_status"] == "credited"
    assert by_kind["attempt_result"]["score"] == 25.0
    assert (await all_changes(cm, student, cursor))[0] == []
    # Повтор пакета після всього — нічого не змінює й у стрічку не потрапляє.
    await ok(await http.post("/sync/events", json=full, headers=student))
    assert (await all_changes(cm, student, cursor))[0] == []


# ---------- 2. тест із вікном через правки, зняття з публікації й переоцінку ----------


def attempt_event(w, answers: dict, completed: dt.datetime) -> dict:
    return ev(
        "test_attempt",
        {"test_id": w.test_id, "answers": answers, "completed_at": iso(completed)},
        completed,
    )


async def regrade(cm, w) -> None:
    async with cm.maker() as db:
        await sync_service.regrade_test(db, uuid.UUID(w.test_id))


async def attempts_of(cm, student_id) -> dict[str, tuple[str, float | None]]:
    async with cm.maker() as db:
        rows = await db.execute(
            select(Attempt.client_event_id, Attempt.credit_status, Attempt.score).where(
                Attempt.student_id == uuid.UUID(student_id)
            )
        )
        return {str(i): (s, None if sc is None else float(sc)) for i, s, sc in rows}


async def test_window_test_across_unpublish_edit_republish_and_regrade(committed, enqueued) -> None:
    cm, http = committed, committed.client
    w = await build_school(cm, window=True)
    t = auth_header(w.teacher)
    student = bearer(await join(cm, w))
    student_id = (await ok(await http.get("/auth/me", headers=student)))["id"]

    # У пакеті ключа відповідей тесту з вікном немає.
    manifest = await ok(
        await http.get("/packs/manifest", params={"class_id": w.class_id}, headers=student)
    )
    pack = await ok(await http.get(f"/packs/{manifest['packs'][0]['id']}", headers=student))
    questions = pack["lessons"][0]["tests"][0]["questions"]
    assert all("answer_key" not in q for q in questions)

    # Урок завершено о t0; спроби: пізня (t0 + 30 год) приходить раніше за вчасну (t0 + 1 год).
    t0 = now() - dt.timedelta(hours=40)
    done = [
        ev(
            "module_progress",
            {"module_id": m, "progress_pct": 100, "completed_at": iso(t0)},
            t0,
        )
        for m in w.modules
    ]
    late = attempt_event(w, {w.q1: ["a"], w.q2: ["b"]}, t0 + dt.timedelta(hours=30))
    early = attempt_event(w, {w.q1: ["a"], w.q2: ["a"]}, t0 + dt.timedelta(hours=1))
    await ok(await http.post("/sync/events", json=batch(late), headers=student))
    assert (await attempts_of(cm, student_id))[late["client_event_id"]][0] == "credited"
    await ok(await http.post("/sync/events", json=batch(*done, early), headers=student))
    got = await attempts_of(cm, student_id)
    assert got[early["client_event_id"]] == ("credited", 25.0)
    assert got[late["client_event_id"]] == ("not_credited_late", 100.0)

    # Вчитель знімає з публікації, міняє ключ q2 і вікно на 48 год, публікує знову.
    await ok(await http.post(f"/lessons/{w.lesson_id}/unpublish", headers=t))
    # Видалити модуль із прогресом учнів не можна.
    r = await http.delete(f"/modules/{w.modules[0]}", headers=t)
    assert r.status_code == 409 and r.json()["error"]["code"] == "IN_USE"
    await ok(await http.patch(f"/questions/{w.q2}", json={"answer_key": ["a"]}, headers=t))
    await ok(await http.patch(f"/tests/{w.test_id}", json={"window_hours": 48}, headers=t))
    regrades = [c for c in enqueued if c.name == "sync.regrade_test"]
    assert len(regrades) == 4  # 2 — нові питання при створенні, 2 — правки
    # Офлайн-подія до уроку, знятого з публікації, однаково приймається (урок був у пакеті).
    t_late = now()
    r = await ok(
        await http.post(
            "/sync/events",
            json=batch(
                ev("module_progress", {"module_id": w.modules[0], "progress_pct": 100}, t_late)
            ),
            headers=student,
        )
    )
    assert r["results"][0]["status"] == "accepted"
    await regrade(cm, w)
    got = await attempts_of(cm, student_id)
    # Нова оцінка: q2 тепер «a» — рання спроба 100 %, пізня 25 %; пізня (30 год) — у вікні 48 год,
    # але вже не перша: «повтор».
    assert got[early["client_event_id"]] == ("credited", 100.0)
    assert got[late["client_event_id"]] == ("not_credited_repeat", 25.0)
    # Повтор переоцінки нічого не змінює.
    cursor = (await all_changes(cm, student))[1]
    await regrade(cm, w)
    assert (await all_changes(cm, student, cursor))[0] == []

    lesson = await ok(await http.post(f"/lessons/{w.lesson_id}/publish", headers=t))
    assert lesson["version"] == 2
    built = await rebuild_packs(cm, w)
    assert built, "republished lesson must produce a new pack version"
    manifest = await ok(
        await http.get("/packs/manifest", params={"class_id": w.class_id}, headers=student)
    )
    today = next(p for p in manifest["packs"] if p["pack_date"] == str(w.today))
    assert today["version"] >= 2
    pack = await ok(await http.get(f"/packs/{today['id']}", headers=student))
    assert pack["lessons"][0]["id"] == w.lesson_id

    # Кабінет учня й вчителя після переоцінки.
    await recompute(cm, student_id, w.class_id)
    mine = await ok(await http.get(f"/students/{student_id}/progress", headers=student))
    assert mine["tests"][0]["score"] == 100.0 and mine["tests"][0]["attempts"] == 2
    tests = await ok(await http.get(f"/classes/{w.class_id}/tests", headers=t))
    assert tests["tests"][0]["window_hours"] == 48
    assert tests["tests"][0]["students"][0]["status"] == "passed"


# ---------- 3. видалення учня посеред роботи ----------


async def test_student_deleted_mid_flow_leaves_nothing_dangling(committed, enqueued) -> None:
    cm, http = committed, committed.client
    w = await build_school(cm)
    t, admin = auth_header(w.teacher), auth_header(w.admin)
    gone = bearer(await join(cm, w, "Іван", "Петренко"))
    stays = bearer(await join(cm, w, "Марко", "Коваль"))
    gone_id = (await ok(await http.get("/auth/me", headers=gone)))["id"]
    stays_id = (await ok(await http.get("/auth/me", headers=stays)))["id"]
    parent_user = await cm.factory.adult("parent", None)
    await cm.session.commit()
    parent = auth_header(parent_user)
    code = (await ok(await http.post(f"/students/{gone_id}/parent-link-codes", headers=t), 201))[
        "code"
    ]
    await ok(await http.post("/parent/link", json={"code": code}, headers=parent))

    # Відкрита перекличка, відмітки й прогрес обох, спроби тесту, push-підписка.
    rc = await ok(
        await http.post(
            f"/classes/{w.class_id}/rollcall", json={"id": str(uuid.uuid4())}, headers=t
        ),
        201,
    )
    t0 = now()
    for headers in (gone, stays):
        await ok(
            await http.post(
                "/sync/events",
                json=batch(
                    ev("rollcall_status", {"session_id": rc["id"], "status": "in_shelter"}, t0),
                    ev("module_progress", {"module_id": w.modules[0], "progress_pct": 100}, t0),
                    attempt_event(w, {w.q1: ["a"], w.q2: ["b"]}, t0),
                ),
                headers=headers,
            )
        )
    async with cm.maker() as db:
        db.add(
            PushSubscription(
                user_id=uuid.UUID(gone_id),
                endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}",
                p256dh="x",
                auth="y",
            )
        )
        await db.commit()
    await recompute(cm, gone_id, w.class_id)
    await recompute(cm, stays_id, w.class_id)
    before = await ok(await http.get(f"/classes/{w.class_id}/progress", headers=t))
    assert before["lessons"][0]["students_total"] == 2

    # Батьки просять видалити, адмін підтверджує.
    req_id = str(uuid.uuid4())
    await ok(
        await http.post(
            f"/students/{gone_id}/deletion-requests",
            json={"id": req_id, "reason": "left_school"},
            headers=parent,
        ),
        201,
    )
    enqueued.clear()
    await ok(await http.post(f"/deletion-requests/{req_id}/confirm", headers=admin))
    assert [c.name for c in enqueued] == ["stats.recompute_class"]

    gone_uuid = uuid.UUID(gone_id)
    async with cm.maker() as db:
        for model, column in (
            (SyncEvent, SyncEvent.user_id),
            (Attempt, Attempt.student_id),
            (ModuleProgress, ModuleProgress.student_id),
            (RollCallStatus, RollCallStatus.student_id),
            (PushSubscription, PushSubscription.user_id),
            (StudentLessonStat, StudentLessonStat.student_id),
            (StudentTestStat, StudentTestStat.student_id),
        ):
            assert await count(db, model, column == gone_uuid) == 0, model.__name__
    # Перекличка класу далі відкрита й показує лише того, хто лишився.
    view = await ok(await http.get(f"/classes/{w.class_id}/rollcall/current", headers=t))
    assert [s["student_id"] for s in view["session"]["students"]] == [stays_id]
    assert view["session"]["summary"] == {"safe": 0, "in_shelter": 1, "no_response": 0}

    # Токени видаленого не діють; його пристрій, що синхронізується пізніше, отримує 401
    # (а не 500), а задачі, поставлені для нього раніше, не падають.
    assert (await http.get("/auth/me", headers=gone)).status_code == 401
    late = await http.post(
        "/sync/events",
        json=batch(ev("module_progress", {"module_id": w.modules[1], "progress_pct": 50}, now())),
        headers=gone,
    )
    assert late.status_code == 401
    async with cm.maker() as db:
        assert await stats_service.recompute_student_rows(db, gone_uuid) == []
    async with cm.maker() as db:
        assert await sync_service.regrade_test(db, uuid.UUID(w.test_id)) == [uuid.UUID(stays_id)]
    async with cm.maker() as db:
        payload = {"type": "rollcall_status", "student_id": gone_id, "session_id": rc["id"]}
        assert await push_service.recipients(db, payload) == []
    # Батьки дитини більше не бачать.
    assert (await http.get(f"/students/{gone_id}/progress", headers=parent)).status_code == 404

    # Агрегати класу перераховані, пакети збираються як раніше.
    await recompute(cm, stays_id, w.class_id)
    after = await ok(await http.get(f"/classes/{w.class_id}/progress", headers=t))
    assert after["lessons"][0]["students_total"] == 1
    tests = await ok(await http.get(f"/classes/{w.class_id}/tests", headers=t))
    assert [s["student_id"] for s in tests["tests"][0]["students"]] == [stays_id]
    gaps = await ok(await http.get(f"/classes/{w.class_id}/gaps", headers=t))
    assert all(q["answered"] == 1 for topic in gaps["topics"] for q in topic["questions"])
    assert await rebuild_packs(cm, w) == []  # вміст не змінився — нової версії немає
    closed = await ok(
        await http.post(f"/classes/{w.class_id}/rollcall/{rc['id']}/close", headers=t)
    )
    assert closed["closed_at"] is not None


# ---------- 4. життєвий цикл токенів ----------


async def refresh(cm, token: str):
    return await cm.client.post(
        "/auth/token", json={"grant_type": "refresh_token", "refresh_token": token}
    )


async def join_raw(cm, w, pin: str, name: str = "Іван", last: str = "Петренко"):
    return await cm.client.post(
        "/auth/student/join",
        json={"join_code": w.join_code, "display_name": name, "last_name": last, "pin": pin},
    )


async def test_token_lifecycle_join_refresh_pin_reset_rejoin_parent_and_deactivation(
    committed,
) -> None:
    cm, http = committed, committed.client
    w = await build_school(cm)
    t = auth_header(w.teacher)
    first = await join(cm, w, pin="1111")
    student_id = (await ok(await http.get("/auth/me", headers=bearer(first))))["id"]

    # Ротація: новий refresh працює; повтор уже ротованого після наступної ротації — крадіжка,
    # відкликається вся родина.
    second = await ok(await refresh(cm, first["refresh_token"]))
    assert second["refresh_token"] != first["refresh_token"]
    third = await ok(await refresh(cm, second["refresh_token"]))
    assert (await refresh(cm, first["refresh_token"])).status_code == 400
    assert (await refresh(cm, third["refresh_token"])).status_code == 400

    # Інший пристрій учня, у його черзі — невідправлені події. Хибний PIN не входить.
    device = await join(cm, w, pin="1111")
    pending = batch(ev("module_progress", {"module_id": w.modules[0], "progress_pct": 40}, now()))
    assert (await join_raw(cm, w, "2222")).status_code == 401

    # Вчитель скидає PIN: старі access і refresh не діють, події лишаються в outbox (401).
    await ok(
        await http.post(f"/classes/{w.class_id}/students/{student_id}/pin-reset", headers=t), 204
    )
    assert (await http.get("/auth/me", headers=bearer(device))).status_code == 401
    assert (await refresh(cm, device["refresh_token"])).status_code == 400
    r = await http.post("/sync/events", json=pending, headers=bearer(device))
    assert r.status_code == 401
    # Повторний вхід задає новий PIN, той самий учень; outbox відправляється.
    rejoined = await join(cm, w, pin="2222")
    assert (await ok(await http.get("/auth/me", headers=bearer(rejoined))))["id"] == student_id
    sent = await ok(await http.post("/sync/events", json=pending, headers=bearer(rejoined)))
    assert sent["results"][0]["status"] == "accepted"
    assert (await join_raw(cm, w, "1111")).status_code == 401

    # Батьки: доступ лише після прив'язки й лише до своєї дитини.
    parent_user = await cm.factory.adult("parent", None)
    await cm.session.commit()
    parent = auth_header(parent_user)
    assert (await http.get(f"/students/{student_id}/progress", headers=parent)).status_code == 403
    code = (await ok(await http.post(f"/students/{student_id}/parent-link-codes", headers=t), 201))[
        "code"
    ]
    await ok(await http.post("/parent/link", json={"code": code}, headers=parent))
    await ok(await http.get(f"/students/{student_id}/progress", headers=parent))
    other = bearer(await join(cm, w, "Марко", "Коваль"))
    other_id = (await ok(await http.get("/auth/me", headers=other)))["id"]
    assert (await http.get(f"/students/{other_id}/progress", headers=parent)).status_code == 403

    # Деактивований учень: access, refresh і вхід відхиляються.
    async with cm.maker() as db:
        user = await db.get(User, uuid.UUID(student_id))
        user.is_active = False
        await db.commit()
    assert (await http.get("/auth/me", headers=bearer(rejoined))).status_code == 401
    assert (await refresh(cm, rejoined["refresh_token"])).status_code == 400
    assert (await join_raw(cm, w, "2222")).status_code == 401


# ---------- 5. паралельність ----------


async def test_two_devices_of_one_student_sync_in_parallel(committed, enqueued) -> None:
    """Телефон і планшет учня відправляють різні події одночасно: прогрес — максимум,
    перекличка — найпізніша за часом пристрою незалежно від порядку commit, зараховано одну
    (найранішу) спробу, батькам — не більше push, ніж справжніх змін, останній — фінальний."""
    cm, http = committed, committed.client
    w = await build_school(cm)
    t = auth_header(w.teacher)
    rc = await ok(
        await http.post(
            f"/classes/{w.class_id}/rollcall", json={"id": str(uuid.uuid4())}, headers=t
        ),
        201,
    )
    phone = bearer(await join(cm, w))
    tablet = bearer(await join(cm, w))
    student_id = (await ok(await http.get("/auth/me", headers=phone)))["id"]
    await cm.factory.parent_of(await cm.session.get(User, uuid.UUID(student_id)))
    await cm.session.commit()
    t0 = now()
    rounds = 5
    bodies = []
    for i in range(rounds):
        for device, headers in ((DEVICE_1, phone), (DEVICE_2, tablet)):
            k = 2 * i + (device == DEVICE_2)
            at = t0 + dt.timedelta(seconds=k)
            status = "in_shelter" if k % 2 else "safe"
            bodies.append(
                (
                    headers,
                    batch(
                        ev(
                            "rollcall_status",
                            {"session_id": rc["id"], "status": status},
                            at,
                            device,
                        ),
                        ev(
                            "module_progress",
                            {"module_id": w.modules[0], "progress_pct": 10 * (k + 1)},
                            at,
                            device,
                        ),
                        attempt_event(w, {w.q1: ["a"]}, at) | {"device_id": device},
                    ),
                )
            )
    responses = await asyncio.gather(
        *[http.post("/sync/events", json=b, headers=h) for h, b in reversed(bodies)]
    )
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    async with cm.maker() as db:
        status = await db.get(RollCallStatus, (uuid.UUID(rc["id"]), uuid.UUID(student_id)))
        assert status.status == "in_shelter"  # k = 9 — найпізніший
        mp = await db.get(ModuleProgress, (uuid.UUID(student_id), uuid.UUID(w.modules[0])))
        assert mp.progress_pct == 100
        credited = list(
            await db.scalars(select(Attempt).where(Attempt.credit_status == "credited"))
        )
        assert len(credited) == 1 and credited[0].completed_at_client == t0
        assert await count(db, Attempt) == 2 * rounds
    sent = [p["status"] for p in pushes(enqueued, "rollcall_status")]
    assert 1 <= len(sent) <= 2 * rounds and sent[-1] in ("in_shelter", "safe")
    view = await ok(await http.get(f"/students/{student_id}/rollcall/current", headers=phone))
    assert view["status"] == "in_shelter"


async def test_teacher_closes_roll_call_while_marks_arrive(committed) -> None:
    """Закриття переклички паралельно з відмітками: відмітки, зроблені до закриття, прийняті
    (і лежать у закритій сесії), зроблені явно після закриття — `session_closed`."""
    cm, http = committed, committed.client
    w = await build_school(cm)
    t = auth_header(w.teacher)
    rc = await ok(
        await http.post(
            f"/classes/{w.class_id}/rollcall", json={"id": str(uuid.uuid4())}, headers=t
        ),
        201,
    )
    students = [bearer(await join(cm, w, f"Учень{i}", "Тестовий")) for i in range(6)]
    t0 = now()
    marks = [
        http.post(
            "/sync/events",
            json=batch(ev("rollcall_status", {"session_id": rc["id"], "status": "in_shelter"}, t0)),
            headers=s,
        )
        for s in students
    ]
    close = http.post(f"/classes/{w.class_id}/rollcall/{rc['id']}/close", headers=t)
    *results, closed = await asyncio.gather(*marks, close)
    assert closed.status_code == 200
    assert all(r.json()["results"][0]["status"] == "accepted" for r in results)
    async with cm.maker() as db:
        assert (
            await count(db, RollCallStatus, RollCallStatus.session_id == uuid.UUID(rc["id"])) == 6
        )
    after_close = now() + dt.timedelta(minutes=10)
    late = await ok(
        await http.post(
            "/sync/events",
            json=batch(
                ev("rollcall_status", {"session_id": rc["id"], "status": "safe"}, after_close),
            ),
            headers=students[0],
        )
    )
    assert late["results"][0] == {
        "client_event_id": late["results"][0]["client_event_id"],
        "status": "rejected",
        "reason": "session_closed",
    }


async def test_pack_rebuild_concurrent_with_unpublish_and_republish(committed) -> None:
    """Періодична перезбірка йде одночасно з правкою уроку: версії пакета не дублюються, а
    після всіх задач найновіша версія дня відповідає останньому стану уроку."""
    cm, http = committed, committed.client
    w = await build_school(cm)
    t = auth_header(w.teacher)

    async def rebuild():
        async with cm.maker() as db:
            return await packs_service.rebuild_class(db, uuid.UUID(w.class_id), get_settings())

    await asyncio.gather(
        rebuild(), http.post(f"/lessons/{w.lesson_id}/unpublish", headers=t), rebuild()
    )
    await rebuild()  # задача, поставлена unpublish
    await ok(
        await http.patch(
            f"/lessons/{w.lesson_id}", json={"title": "Дроби (нова версія)"}, headers=t
        )
    )
    results = await asyncio.gather(
        rebuild(), http.post(f"/lessons/{w.lesson_id}/publish", headers=t), rebuild()
    )
    assert results[1].status_code == 200
    await rebuild()  # задача, поставлена publish
    assert await rebuild() == []  # ідемпотентно

    student = bearer(await join(cm, w))
    manifest = await ok(
        await http.get("/packs/manifest", params={"class_id": w.class_id}, headers=student)
    )
    today = next(p for p in manifest["packs"] if p["pack_date"] == str(w.today))
    pack = await ok(await http.get(f"/packs/{today['id']}", headers=student))
    assert [(item["id"], item["title"]) for item in pack["lessons"]] == [
        (w.lesson_id, "Дроби (нова версія)")
    ]
    async with cm.maker() as db:
        from app.models.packs import KnowledgePack

        versions = list(
            await db.scalars(
                select(KnowledgePack.version)
                .where(
                    KnowledgePack.class_id == uuid.UUID(w.class_id),
                    KnowledgePack.pack_date == w.today,
                )
                .order_by(KnowledgePack.version)
            )
        )
    assert versions == list(range(1, len(versions) + 1))


# ---------- 6. час: перехід на зимовий/літній час, зсув годинника пристрою ----------


async def test_schedule_and_current_lesson_across_kyiv_dst_change(client, factory, world) -> None:
    """25.10.2026 Київ переходить з UTC+3 на UTC+2: урок о 09:00 за Києвом — 06:00 UTC у суботу
    й 07:00 UTC у неділю; «урок зараз» визначається за місцевим часом."""
    from app.models.school import ScheduleSlot

    subject = await factory.subject()
    slots = [
        ScheduleSlot(
            class_id=world.class_a.id,
            subject_id=subject.id,
            weekday=weekday,
            starts_at=dt.time(9, 0),
            ends_at=dt.time(9, 45),
            valid_from=dt.date(2026, 3, 1),
        )
        for weekday in (6, 7)
    ]
    factory.session.add_all(slots)
    await factory.session.flush()
    headers = auth_header(world.teacher_a)
    r = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": "2026-10-24", "days": 2},
        headers=headers,
    )
    days = r.json()["days"]
    assert [d["items"][0]["starts_at_utc"] for d in days] == [
        "2026-10-24T06:00:00Z",
        "2026-10-25T07:00:00Z",
    ]

    async def current(at: str) -> dict | None:
        r = await client.get(
            f"/classes/{world.class_a.id}/schedule/current", params={"at": at}, headers=headers
        )
        assert r.status_code == 200, r.text
        return r.json()["item"]

    assert await current("2026-10-24T06:30:00Z") is not None
    assert await current("2026-10-25T06:30:00Z") is None  # 08:30 за Києвом
    assert await current("2026-10-25T07:30:00Z") is not None  # 09:30 за Києвом
    # Весною (29.03.2026): 09:00 за Києвом — 07:00 UTC до переходу й 06:00 UTC після.
    r = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": "2026-03-28", "days": 2},
        headers=headers,
    )
    assert [d["items"][0]["starts_at_utc"] for d in r.json()["days"]] == [
        "2026-03-28T07:00:00Z",
        "2026-03-29T06:00:00Z",
    ]


async def test_device_clock_skew_both_directions(client, db_session, world, factory) -> None:
    """Годинник пристрою відстає на добу або поспішає на 2 години: події приймаються,
    позначаються підозрілими, відмітка переклички, зроблена до закриття за годинником
    сервера, не губиться; «Як ти зараз?» датується виправленим часом."""
    from app.models.rollcall import RollCallSession
    from app.models.wellbeing import WellbeingAnswer

    rc = RollCallSession(class_id=world.class_a.id, opened_at=now() - dt.timedelta(hours=1))
    db_session.add(rc)
    await db_session.flush()
    real = now()
    behind = real - dt.timedelta(days=1)
    r = await client.post(
        "/sync/events",
        json=batch(
            ev("rollcall_status", {"session_id": str(rc.id), "status": "in_shelter"}, behind),
            ev("survey_answer", {"value": 3}, behind),
            sent_at=behind,
        ),
        headers=auth_header(world.student_a),
    )
    assert [x["status"] for x in r.json()["results"]] == ["accepted", "accepted"]
    answer = await db_session.scalar(
        select(WellbeingAnswer).where(WellbeingAnswer.student_id == world.student_a.id)
    )
    assert answer is not None and answer.answered_on == real.astimezone(KYIV).date()
    events = list(await db_session.scalars(select(SyncEvent)))
    assert all(e.is_suspicious for e in events)

    # Поспішає на 2 год: відмітка «зараз» після закриття сесії 1 хв тому — за виправленим
    # часом вона до закриття + допуску, тож приймається.
    rc.closed_at = real - dt.timedelta(minutes=1)
    await db_session.flush()
    ahead = real + dt.timedelta(hours=2)
    r = await client.post(
        "/sync/events",
        json=batch(
            ev(
                "rollcall_status",
                {"session_id": str(rc.id), "status": "safe"},
                ahead - dt.timedelta(minutes=2),
            ),
            sent_at=ahead,
        ),
        headers=auth_header(world.student_a),
    )
    assert r.json()["results"][0]["status"] == "accepted"


# ---------- 7–8. запуск і контракт ----------


def test_beat_and_enqueued_task_names_are_registered() -> None:
    """Beat і `enqueue(...)` посилаються на задачі за іменем: опечатка — задача, яку ніхто не
    виконує. Усі імена мають бути зареєстровані в застосунку Celery."""
    import re
    from pathlib import Path

    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks)
    for name, entry in celery_app.conf.beat_schedule.items():
        assert entry["task"] in registered, name
    sent: set[str] = set()
    for path in (Path(__file__).resolve().parent.parent / "app").rglob("*.py"):
        sent |= set(re.findall(r'enqueue\(\s*"([a-z_.]+)"', path.read_text(encoding="utf-8")))
    assert sent and sent <= registered, sent - registered


# Маршрути без автентифікації — свідомо публічні: перевірка стану, вхід, обмін токенів.
PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("GET", "/version"),
    ("POST", "/auth/authorize"),
    ("POST", "/auth/token"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/student/join"),
}


def test_every_route_requires_auth_unless_explicitly_public() -> None:
    from fastapi.routing import APIRoute

    from app.api.deps import get_current_user
    from app.main import create_app

    def protected(dependant) -> bool:
        return dependant.call is get_current_user or any(
            protected(d) for d in dependant.dependencies
        )

    def routes(items):
        for r in items:
            if isinstance(r, APIRoute):
                yield r
            else:
                nested = getattr(r, "routes", None) or getattr(
                    getattr(r, "original_router", None), "routes", None
                )
                if nested:
                    yield from routes(nested)

    found = list(routes(create_app().routes))
    assert len(found) > 80
    public = {(method, r.path) for r in found if not protected(r.dependant) for method in r.methods}
    assert public == PUBLIC_ROUTES
