"""Тривоги: опитування API (фейковий провайдер), реакція, ручна кнопка, активні, журнал."""

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

import httpx
import pytest
from conftest import auth_header, pushes
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.alerts import AlertEvent, AlertSource
from app.models.lessons import Lesson
from app.models.rollcall import RollCallSession
from app.models.school import LessonAssignment, ScheduleSlot, School
from app.services import alerts as service
from app.services.alert_provider import (
    ActiveAlerts,
    AlertProvider,
    AlertProviderError,
    AlertsInUaProvider,
    ProviderAlert,
    parse_alerts_in_ua,
)
from app.workers import alerts as alerts_worker

pytestmark = pytest.mark.anyio

KYIV = ZoneInfo("Europe/Kyiv")


class FakeProvider(AlertProvider):
    name = AlertsInUaProvider.name

    def __init__(self, alerts: list[ProviderAlert] | None = None) -> None:
        self.alerts = alerts or []
        self.error: str | None = None
        self.complete = True

    async def active_alerts(self) -> ActiveAlerts:
        if self.error:
            raise AlertProviderError(self.error)
        return ActiveAlerts(list(self.alerts), complete=self.complete)


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def api_alert(external_id: str = "101", region: str = "kyiv") -> ProviderAlert:
    return ProviderAlert(
        external_id=external_id, region_code=region, started_at=now() - dt.timedelta(minutes=1)
    )


async def lesson_now(factory, world, klass) -> Lesson:
    """Урок, що йде в класі зараз (слот на весь день сьогодні за Києвом)."""
    db = factory.session
    subject = await factory.subject()
    today = now().astimezone(KYIV).date()
    slot = ScheduleSlot(
        class_id=klass.id,
        subject_id=subject.id,
        weekday=today.isoweekday(),
        starts_at=dt.time(0, 0),
        ends_at=dt.time(23, 59, 59),
        valid_from=today - dt.timedelta(days=1),
    )
    lesson = Lesson(
        subject_id=subject.id,
        author_id=world.teacher_a.id,
        title="Дроби",
        shelter_part="Укриття",
        main_part="Основна",
        status="published",
        published_at=now(),
    )
    db.add_all([slot, lesson])
    await db.flush()
    db.add(LessonAssignment(slot_id=slot.id, date=today, lesson_id=lesson.id))
    await db.flush()
    return lesson


async def count(db: AsyncSession, model, *where) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*where)) or 0


@pytest.fixture
def enabled_settings(app: FastAPI):
    """Опитування «увімкнене» (є токен) — щоб source_available залежав від стану джерела."""
    settings = get_settings().model_copy(update={"alerts_api_token": SecretStr("t0ken")})
    app.dependency_overrides[get_settings] = lambda: settings
    return settings


# ---------- опитування API ----------


async def test_poll_journals_alert_for_every_school_of_region_and_reacts(
    db_session, factory, world, enqueued
) -> None:
    lviv = await factory.school("Львівська школа")
    lviv.region_code = "lviv"
    lesson = await lesson_now(factory, world, world.class_a)
    provider = FakeProvider([api_alert()])

    result = await service.poll(db_session, provider)
    assert result["started"] == 2  # обидві школи регіону kyiv

    rows = (await db_session.scalars(select(AlertEvent))).all()
    assert {r.school_id for r in rows} == {world.school.id, world.other_school.id}
    assert all(r.source == "api" and r.external_id == "101" and r.ended_at is None for r in rows)

    # Урок зараз лише в 7-А: перекличка й push з id уроку лише для нього.
    sessions = (await db_session.scalars(select(RollCallSession))).all()
    assert [s.class_id for s in sessions] == [world.class_a.id]
    assert sessions[0].closed_at is None and sessions[0].is_drill is False
    alert_push = pushes(enqueued, "alert")
    assert alert_push == [
        {
            "type": "alert",
            "class_id": str(world.class_a.id),
            "alert_id": str(sessions[0].alert_event_id),
            "lesson_id": str(lesson.id),
        }
    ]
    assert all(c.queue == "push" for c in enqueued)

    state = await db_session.get(AlertSource, AlertsInUaProvider.name)
    assert state.last_success_at is not None and state.last_error is None


async def test_repeated_poll_is_idempotent(db_session, factory, world, enqueued) -> None:
    await lesson_now(factory, world, world.class_a)
    provider = FakeProvider([api_alert()])
    await service.poll(db_session, provider)
    # Повторна доставка тієї самої тривоги (наступний цикл, паралельний запуск задачі).
    again = await service.poll(db_session, provider)
    assert again["started"] == 0 and again["ended"] == 0
    assert await count(db_session, AlertEvent) == 2
    assert await count(db_session, RollCallSession) == 1
    assert len(pushes(enqueued)) == 1


async def test_alert_end_closes_rollcall_once(db_session, factory, world, enqueued) -> None:
    await lesson_now(factory, world, world.class_a)
    provider = FakeProvider([api_alert()])
    await service.poll(db_session, provider)

    provider.alerts = []  # відбій: тривоги більше немає серед активних
    ended = await service.poll(db_session, provider)
    assert ended["ended"] == 2
    rows = (await db_session.scalars(select(AlertEvent))).all()
    assert all(r.ended_at is not None for r in rows)
    session_row = await db_session.scalar(select(RollCallSession))
    assert session_row.closed_at is not None
    assert pushes(enqueued, "all_clear") == [
        {
            "type": "all_clear",
            "class_id": str(world.class_a.id),
            "alert_id": str(session_row.alert_event_id),
        }
    ]

    again = await service.poll(db_session, provider)
    assert again["ended"] == 0
    assert len(pushes(enqueued, "all_clear")) == 1


async def test_incomplete_response_does_not_end_alerts(
    db_session, factory, world, enqueued
) -> None:
    await lesson_now(factory, world, world.class_a)
    provider = FakeProvider([api_alert()])
    await service.poll(db_session, provider)

    # Запис тривоги не пройшов валідацію: її немає серед активних, але це не відбій.
    provider.alerts, provider.complete = [], False
    for _ in range(2):  # і повтор опитування теж
        result = await service.poll(db_session, provider)
        assert result["ended"] == 0
    assert await count(db_session, AlertEvent, AlertEvent.ended_at.is_(None)) == 2
    assert await count(db_session, RollCallSession, RollCallSession.closed_at.is_(None)) == 1
    assert pushes(enqueued, "all_clear") == []

    provider.complete = True  # повна відповідь без тривоги — відбій
    assert (await service.poll(db_session, provider))["ended"] == 2
    assert len(pushes(enqueued, "all_clear")) == 1


async def test_rollcall_stays_open_while_another_alert_covers_class(
    client: AsyncClient, db_session, factory, world, enqueued
) -> None:
    await lesson_now(factory, world, world.class_a)
    provider = FakeProvider([api_alert()])
    await service.poll(db_session, provider)
    api_alert_id = await db_session.scalar(
        select(AlertEvent.id).where(AlertEvent.school_id == world.school.id)
    )
    body = {"id": str(uuid.uuid4()), "class_id": str(world.class_a.id), "is_drill": False}
    resp = await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    assert resp.status_code == 201

    # Тривога з API (до якої прив'язана сесія) закінчилась, ручна ще триває.
    provider.alerts = []
    await service.poll(db_session, provider)
    session_row = await db_session.scalar(
        select(RollCallSession).execution_options(populate_existing=True)
    )
    assert session_row.closed_at is None
    assert session_row.alert_event_id == uuid.UUID(body["id"])
    assert session_row.alert_event_id != api_alert_id
    assert pushes(enqueued, "all_clear") == []
    assert (await service.poll(db_session, provider))["ended"] == 0  # повтор нічого не міняє

    # Відбій останньої тривоги закриває перекличку й шле один «відбій».
    url = f"/alerts/{body['id']}/end"
    assert (await client.post(url, headers=auth_header(world.teacher_a))).status_code == 200
    assert (await client.post(url, headers=auth_header(world.teacher_a))).status_code == 200
    await db_session.refresh(session_row)
    assert session_row.closed_at is not None
    assert pushes(enqueued, "all_clear") == [
        {"type": "all_clear", "class_id": str(world.class_a.id), "alert_id": body["id"]}
    ]


async def test_provider_failure_keeps_alerts_and_marks_source(
    db_session, world, app, enabled_settings
) -> None:
    provider = FakeProvider([api_alert()])
    t0 = now()
    await service.poll(db_session, provider, now=t0)
    assert await service.source_available(db_session, enabled_settings, now=t0)

    provider.error = "http_503"
    result = await service.poll(db_session, provider, now=t0 + dt.timedelta(seconds=30))
    assert result == {"error": "http_503"}
    # Збій API — не відбій: тривоги лишаються активними.
    assert await count(db_session, AlertEvent, AlertEvent.ended_at.is_(None)) == 2
    state = await db_session.get(AlertSource, AlertsInUaProvider.name)
    assert state.last_error == "http_503" and state.last_success_at == t0

    stale = t0 + dt.timedelta(seconds=enabled_settings.alerts_source_stale_s + 1)
    assert not await service.source_available(db_session, enabled_settings, now=stale)


async def test_alert_reappearing_after_end_is_reopened(
    db_session, factory, world, enqueued
) -> None:
    await lesson_now(factory, world, world.class_a)
    provider = FakeProvider([api_alert()])
    await service.poll(db_session, provider)
    provider.alerts = []
    await service.poll(db_session, provider)
    provider.alerts = [api_alert()]
    result = await service.poll(db_session, provider)
    assert result["reopened"] == 2 and result["started"] == 0
    assert await count(db_session, AlertEvent) == 2
    assert await count(db_session, AlertEvent, AlertEvent.ended_at.is_(None)) == 2
    # Нова сесія переклички й новий push «тривога».
    assert await count(db_session, RollCallSession, RollCallSession.closed_at.is_(None)) == 1
    assert len(pushes(enqueued, "alert")) == 2


def test_parse_alerts_in_ua_filters_and_validates() -> None:
    data = {
        "alerts": [
            {
                "id": 8757,
                "location_title": "м. Київ",
                "location_type": "oblast",
                "started_at": "2026-11-05T09:30:00.000Z",
                "finished_at": None,
                "alert_type": "air_raid",
                "location_uid": "31",
            },
            {  # район — не тривога всієї області
                "id": 8758,
                "location_type": "raion",
                "started_at": "2026-11-05T09:30:00.000Z",
                "location_uid": "120",
            },
            {"id": 1, "location_type": "oblast"},  # невалідний запис пропускається
        ]
    }
    assert parse_alerts_in_ua(data) == ActiveAlerts(
        [ProviderAlert("8757", "31", dt.datetime(2026, 11, 5, 9, 30, tzinfo=dt.UTC))],
        complete=False,
    )
    with pytest.raises(AlertProviderError):
        parse_alerts_in_ua({"unexpected": True})


def test_parse_alerts_in_ua_accepts_region_cities_only() -> None:
    def record(id_: int, location_type: str, uid: str) -> dict:
        return {
            "id": id_,
            "location_type": location_type,
            "location_uid": uid,
            "started_at": "2026-11-05T09:30:00Z",
        }

    data = {
        "alerts": [
            record(1, "city", "31"),  # м. Київ — окремий регіон
            record(2, "city", "30"),  # м. Севастополь — окремий регіон
            record(3, "city", "1293"),  # звичайне місто — частина області
            record(4, "hromada", "1500"),
            record(5, "oblast", "14"),
        ]
    }
    result = parse_alerts_in_ua(data)
    assert result.complete is True
    assert [(a.external_id, a.region_code) for a in result.alerts] == [
        ("1", "31"),
        ("2", "30"),
        ("5", "14"),
    ]


async def test_alerts_in_ua_provider_http(enabled_settings) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"alerts": []})

    provider = AlertsInUaProvider(enabled_settings, transport=httpx.MockTransport(handler))
    assert await provider.active_alerts() == ActiveAlerts([])
    assert seen[0].headers["Authorization"] == "Bearer t0ken"
    assert str(seen[0].url) == enabled_settings.alerts_api_url

    limited = AlertsInUaProvider(
        enabled_settings, transport=httpx.MockTransport(lambda r: httpx.Response(429))
    )
    with pytest.raises(AlertProviderError) as exc:
        await limited.active_alerts()
    assert exc.value.reason == "http_429" and "t0ken" not in str(exc.value)


def test_poll_task_disabled_without_token() -> None:
    assert alerts_worker.poll() == {"skipped": "disabled"}


# ---------- ручна тривога ----------


def manual_body(klass, **kw) -> dict:
    return {"id": str(kw.get("id", uuid.uuid4())), "class_id": str(klass.id), "is_drill": True}


async def test_teacher_manual_drill_is_idempotent(
    client: AsyncClient, db_session, factory, world, enqueued
) -> None:
    lesson = await lesson_now(factory, world, world.class_a)
    body = manual_body(world.class_a)
    first = await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["source"] == "manual" and data["is_drill"] is True
    assert data["class_id"] == str(world.class_a.id)
    assert data["school_id"] == str(world.school.id) and data["region_code"] == "kyiv"

    session_row = await db_session.scalar(select(RollCallSession))
    assert session_row.is_drill is True and session_row.opened_by == world.teacher_a.id
    assert pushes(enqueued) == [
        {
            "type": "alert",
            "class_id": str(world.class_a.id),
            "alert_id": body["id"],
            "lesson_id": str(lesson.id),
        }
    ]

    # Повтор (обрив до відповіді) — та сама тривога, без нового push і переклички.
    again = await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    assert again.status_code == 200 and again.json() == data
    assert len(pushes(enqueued)) == 1
    assert await count(db_session, RollCallSession) == 1

    # Той самий id для іншого класу — 409.
    conflict = await client.post(
        "/alerts/manual",
        json={**body, "class_id": str(world.class_b.id)},
        headers=auth_header(world.teacher_b),
    )
    assert conflict.status_code == 409


async def test_manual_alert_without_lesson_still_opens_rollcall(
    client: AsyncClient, db_session, world, enqueued
) -> None:
    resp = await client.post(
        "/alerts/manual", json=manual_body(world.class_a), headers=auth_header(world.admin)
    )
    assert resp.status_code == 201
    assert await count(db_session, RollCallSession) == 1
    assert pushes(enqueued)[0]["lesson_id"] is None


@pytest.mark.parametrize("role", ["teacher_b", "student_a", "parent_a", "other_admin"])
async def test_manual_alert_forbidden(client: AsyncClient, world, role, enqueued) -> None:
    resp = await client.post(
        "/alerts/manual", json=manual_body(world.class_a), headers=auth_header(getattr(world, role))
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    assert enqueued == []


async def test_manual_alert_unknown_class(client: AsyncClient, world) -> None:
    body = {"id": str(uuid.uuid4()), "class_id": str(uuid.uuid4())}
    resp = await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    assert resp.status_code == 404


async def test_end_manual_alert(client: AsyncClient, db_session, world, enqueued) -> None:
    body = manual_body(world.class_a)
    await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    url = f"/alerts/{body['id']}/end"

    denied = await client.post(url, headers=auth_header(world.teacher_b))
    assert denied.status_code == 403

    ended = await client.post(url, headers=auth_header(world.teacher_a))
    assert ended.status_code == 200, ended.text
    assert ended.json()["ended_at"] is not None
    session_row = await db_session.scalar(select(RollCallSession))
    assert session_row.closed_at is not None
    assert len(pushes(enqueued, "all_clear")) == 1

    # Повтор відбою (адміном школи) — та сама відповідь, без нового push.
    again = await client.post(url, headers=auth_header(world.admin))
    assert again.status_code == 200 and again.json() == ended.json()
    assert len(pushes(enqueued, "all_clear")) == 1

    missing = await client.post(f"/alerts/{uuid.uuid4()}/end", headers=auth_header(world.admin))
    assert missing.status_code == 404


async def test_api_alert_cannot_be_ended_manually(client: AsyncClient, db_session, world) -> None:
    await service.poll(db_session, FakeProvider([api_alert()]))
    alert_id = await db_session.scalar(
        select(AlertEvent.id).where(AlertEvent.school_id == world.school.id)
    )
    url = f"/alerts/{alert_id}/end"
    assert (await client.post(url, headers=auth_header(world.teacher_a))).status_code == 403
    assert (await client.post(url, headers=auth_header(world.other_admin))).status_code == 403
    resp = await client.post(url, headers=auth_header(world.admin))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ALERT_NOT_MANUAL"


# ---------- активні тривоги й журнал ----------


async def _alerts_setup(client: AsyncClient, db_session, world) -> dict[str, str]:
    await service.poll(db_session, FakeProvider([api_alert()]))
    api_id = await db_session.scalar(
        select(AlertEvent.id).where(AlertEvent.school_id == world.school.id)
    )
    a = manual_body(world.class_a)
    b = manual_body(world.class_b)
    await client.post("/alerts/manual", json=a, headers=auth_header(world.teacher_a))
    await client.post("/alerts/manual", json=b, headers=auth_header(world.teacher_b))
    return {"api": str(api_id), "a": a["id"], "b": b["id"]}


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("student_a", {"api", "a"}),
        ("teacher_a", {"api", "a"}),
        ("parent_a", {"api", "a"}),
        ("teacher_b", {"api", "b"}),
        ("admin", {"api", "a", "b"}),
        ("parent_free", set()),
    ],
)
async def test_active_alerts_scope(client: AsyncClient, db_session, world, role, expected) -> None:
    ids = await _alerts_setup(client, db_session, world)
    resp = await client.get("/alerts/active", headers=auth_header(getattr(world, role)))
    assert resp.status_code == 200
    got = {a["id"] for a in resp.json()["alerts"]}
    assert got == {ids[k] for k in expected}
    # Опитування в тестах вимкнене (немає токена) → джерело недоступне.
    assert resp.json()["source_available"] is False


async def test_active_alerts_other_school_not_visible(
    client: AsyncClient, db_session, world
) -> None:
    ids = await _alerts_setup(client, db_session, world)
    resp = await client.get("/alerts/active", headers=auth_header(world.other_admin))
    got = {a["id"] for a in resp.json()["alerts"]}
    assert not got & {ids["a"], ids["b"], ids["api"]}
    # Тривога з API для школи 2 (той самий регіон) — своя, окремим рядком.
    assert len(got) == 1


async def test_active_alerts_source_available(
    client: AsyncClient, db_session, world, enabled_settings
) -> None:
    await service.poll(db_session, FakeProvider([]))
    resp = await client.get("/alerts/active", headers=auth_header(world.student_a))
    assert resp.json() == {"alerts": [], "source_available": True}


async def test_alert_journal(client: AsyncClient, db_session, world) -> None:
    ids = await _alerts_setup(client, db_session, world)
    other = School(name="Інший регіон", region_code="lviv")
    db_session.add(other)
    await db_session.flush()
    resp = await client.get("/alerts", headers=auth_header(world.admin))
    assert resp.status_code == 200
    rows = resp.json()
    assert {r["id"] for r in rows} == set(ids.values())
    starts = [r["started_at"] for r in rows]
    assert starts == sorted(starts, reverse=True)

    today = now().astimezone(KYIV).date()
    future = await client.get(
        f"/alerts?from={today + dt.timedelta(days=1)}", headers=auth_header(world.admin)
    )
    assert future.json() == []
    limited = await client.get(f"/alerts?to={today}&limit=1", headers=auth_header(world.admin))
    assert len(limited.json()) == 1

    other_admin = await client.get("/alerts", headers=auth_header(world.other_admin))
    assert {r["id"] for r in other_admin.json()}.isdisjoint(set(ids.values()))
    forbidden = await client.get("/alerts", headers=auth_header(world.teacher_a))
    assert forbidden.status_code == 403


async def test_alert_adopts_manual_and_drill_rollcall(
    client: AsyncClient, db_session, factory, world, enqueued
) -> None:
    """Справжня тривога забирає відкриту перекличку без тривоги (ручний старт) чи навчальну:
    сесія стає не навчальною, а відбій тривоги її закриває."""
    await lesson_now(factory, world, world.class_a)
    h = auth_header(world.teacher_a)
    manual_id = str(uuid.uuid4())
    started = await client.post(
        f"/classes/{world.class_a.id}/rollcall", json={"id": manual_id, "is_drill": True}, headers=h
    )
    assert started.status_code == 201, started.text

    provider = FakeProvider([api_alert()])
    await service.poll(db_session, provider)
    row = await db_session.get(RollCallSession, uuid.UUID(manual_id), populate_existing=True)
    assert row.is_drill is False and row.alert_event_id is not None
    assert await count(db_session, RollCallSession) == 1

    provider.alerts = []
    await service.poll(db_session, provider)
    await db_session.refresh(row)
    assert row.closed_at is not None
    assert [p["class_id"] for p in pushes(enqueued, "all_clear")] == [str(world.class_a.id)]

    # Навчальна ручна тривога не забирає сесію справжньої, а справжня — забирає навчальну.
    drill = await client.post("/alerts/manual", json=manual_body(world.class_a), headers=h)
    assert drill.status_code == 201
    await service.poll(db_session, FakeProvider([api_alert("202")]))
    open_row = await db_session.scalar(
        select(RollCallSession)
        .where(RollCallSession.closed_at.is_(None))
        .execution_options(populate_existing=True)
    )
    assert open_row.is_drill is False and open_row.alert_event_id != uuid.UUID(drill.json()["id"])
    second = await client.post("/alerts/manual", json=manual_body(world.class_a), headers=h)
    assert second.status_code == 201
    await db_session.refresh(open_row)
    assert open_row.is_drill is False


# ---------- автозакриття забутих ручних тривог і перекличок ----------


async def test_forgotten_manual_alert_is_closed_with_all_clear(
    client: AsyncClient, db_session, world, enqueued
) -> None:
    body = manual_body(world.class_a)
    await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    settings = get_settings()

    # Ще не забута: нічого не закривається.
    early = await service.auto_close_stale(db_session, settings, now() + dt.timedelta(hours=1))
    assert early == {"alerts": 0, "rollcalls": 0, "pushes": 0}

    later = now() + dt.timedelta(hours=settings.alerts_manual_max_hours, minutes=1)
    assert (await service.auto_close_stale(db_session, settings, later))["alerts"] == 1
    alert = await db_session.get(AlertEvent, uuid.UUID(body["id"]), populate_existing=True)
    assert alert.ended_at == later
    rc = await db_session.scalar(select(RollCallSession))
    await db_session.refresh(rc)
    assert rc.closed_at == later
    assert pushes(enqueued, "all_clear") == [
        {"type": "all_clear", "class_id": str(world.class_a.id), "alert_id": body["id"]}
    ]

    # Повтор нічого не змінює й не шле вдруге.
    again = await service.auto_close_stale(db_session, settings, later)
    assert again == {"alerts": 0, "rollcalls": 0, "pushes": 0}
    assert len(pushes(enqueued, "all_clear")) == 1


async def test_manual_alert_is_kept_while_api_alert_covers_school(
    client: AsyncClient, db_session, world, enqueued
) -> None:
    body = manual_body(world.class_a)
    await client.post("/alerts/manual", json=body, headers=auth_header(world.teacher_a))
    db_session.add(
        AlertEvent(
            region_code="kyiv",
            school_id=world.school.id,
            source="api",
            external_id="777",
            is_drill=False,
            started_at=now(),
        )
    )
    await db_session.flush()
    later = now() + dt.timedelta(hours=7)
    result = await service.auto_close_stale(db_session, get_settings(), later)
    assert result["alerts"] == 0
    alert = await db_session.get(AlertEvent, uuid.UUID(body["id"]), populate_existing=True)
    assert alert.ended_at is None
    assert pushes(enqueued, "all_clear") == []


async def test_forgotten_manual_rollcall_is_closed_without_push(
    client: AsyncClient, db_session, world, enqueued
) -> None:
    sid = uuid.uuid4()
    resp = await client.post(
        f"/classes/{world.class_a.id}/rollcall",
        json={"id": str(sid)},
        headers=auth_header(world.teacher_a),
    )
    assert resp.status_code == 201, resp.text
    later = now() + dt.timedelta(hours=7)
    result = await service.auto_close_stale(db_session, get_settings(), later)
    assert result == {"alerts": 0, "rollcalls": 1, "pushes": 0}
    rc = await db_session.get(RollCallSession, sid, populate_existing=True)
    assert rc.closed_at == later
    assert pushes(enqueued) == []


def test_auto_close_is_scheduled() -> None:
    from app.workers.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["alerts-auto-close"]
    assert entry["task"] == "alerts.auto_close"
    assert "alerts.auto_close" in celery_app.tasks
