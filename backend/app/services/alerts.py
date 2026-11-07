"""Тривоги (B7): опитування API, журнал, ручна кнопка, реакція, активні тривоги.

Реакція на початок тривоги: класи, у яких зараз урок → сесія переклички (B12, лише рядок) +
push «тривога, відкрий урок» з id уроку (B8, лише постановка в чергу). Та сама реакція — для
класу, у якого урок почався, коли тривога вже йшла (`react_lesson_starts`, beat щохвилини).
Відбій закриває сесії переклички цієї тривоги й ставить push «відбій», якщо клас не покриває
інша активна тривога (тоді сесія переходить до неї й лишається відкритою).

Усі кроки ідемпотентні: повтор опитування, паралельні опитування й повтор ручної тривоги
не створюють дублів (унікальні індекси + ON CONFLICT DO NOTHING, UPDATE ... WHERE ended_at
IS NULL RETURNING). Push ставляться в чергу лише після commit.
"""

import datetime as dt
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.alerts import AlertEvent, AlertSource
from app.models.rollcall import RollCallSession
from app.models.school import ClassMembership, ParentChild, School, SchoolClass, User
from app.schemas.alerts import ManualAlertCreate
from app.services import auth as auth_service
from app.services import school as school_service
from app.services.alert_provider import AlertProvider, AlertProviderError, AlertsInUaProvider
from app.services.idempotency import insert_or_get
from app.services.schedule import DEFAULT_TZ
from app.workers.push import enqueue_push

logger = logging.getLogger(__name__)

# Джерело, стан якого показуємо в `source_available`.
SOURCE_NAME = AlertsInUaProvider.name

_API_KEY = ["source", "region_code", "external_id", "school_id"]
_API_KEY_WHERE = text("external_id IS NOT NULL")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass
class Pushes:
    """Push, які треба поставити в чергу після commit."""

    items: list[dict[str, Any]] = field(default_factory=list)

    def add(self, push_type: str, class_id: uuid.UUID, **ids: Any) -> None:
        self.items.append({"push_type": push_type, "class_id": class_id, **ids})

    async def send(self) -> None:
        for item in self.items:
            await enqueue_push(**item)


# ---------- реакція на тривогу ----------


async def open_rollcall(
    session: AsyncSession,
    class_id: uuid.UUID,
    alert: AlertEvent,
    at: dt.datetime,
    opened_by: uuid.UUID | None = None,
) -> bool:
    """Відкриває сесію переклички класу, якщо відкритої ще немає (одна на клас). B12 додасть
    відмітки; тут лише рядок сесії."""
    stmt = (
        pg_insert(RollCallSession)
        .values(
            id=uuid.uuid4(),
            class_id=class_id,
            alert_event_id=alert.id,
            opened_by=opened_by,
            is_drill=alert.is_drill,
            opened_at=at,
        )
        .on_conflict_do_nothing(index_elements=["class_id"], index_where=text("closed_at IS NULL"))
        .returning(RollCallSession.id)
    )
    if await session.scalar(stmt) is not None:
        return True
    # Відкрита сесія вже є. Ручна перекличка вчителя (без тривоги) чи сесія навчальної тривоги
    # переходить до справжньої тривоги: інакше під час тривоги перекличка лишалася б
    # «навчальною», а відбій її не закрив би (закриваються лише сесії тривоги). Відмітки учнів
    # зберігаються.
    adopt = RollCallSession.alert_event_id.is_(None)
    if not alert.is_drill:
        adopt = or_(adopt, RollCallSession.is_drill)
    await session.execute(
        update(RollCallSession)
        .where(
            RollCallSession.class_id == class_id,
            RollCallSession.closed_at.is_(None),
            adopt,
        )
        .values(alert_event_id=alert.id, is_drill=alert.is_drill)
    )
    return False


async def _covering_alert(
    session: AsyncSession, class_id: uuid.UUID, school_id: uuid.UUID
) -> AlertEvent | None:
    """Найраніша активна тривога, що покриває клас: ручна цього класу або з API його школи."""
    return await session.scalar(
        select(AlertEvent)
        .where(
            AlertEvent.ended_at.is_(None),
            or_(
                AlertEvent.class_id == class_id,
                and_(AlertEvent.class_id.is_(None), AlertEvent.school_id == school_id),
            ),
        )
        .order_by(AlertEvent.started_at, AlertEvent.id)
        .limit(1)
    )


async def _close_rollcalls(
    session: AsyncSession, alert_ids: list[uuid.UUID], at: dt.datetime
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Відкриті сесії переклички завершених тривог: якщо клас покриває інша активна тривога —
    сесія переходить до неї (лишається відкритою, push «відбій» немає); інакше закривається.
    Повертає (class_id, alert_id) закритих. Викликати після запису `ended_at`."""
    if not alert_ids:
        return []
    rows = await session.execute(
        select(RollCallSession.id, RollCallSession.class_id, SchoolClass.school_id)
        .join(SchoolClass, SchoolClass.id == RollCallSession.class_id)
        .where(RollCallSession.alert_event_id.in_(alert_ids), RollCallSession.closed_at.is_(None))
        .order_by(RollCallSession.id)
        .with_for_update(of=RollCallSession)
    )
    closed: list[tuple[uuid.UUID, uuid.UUID]] = []
    for session_id, class_id, school_id in rows.all():
        other = await _covering_alert(session, class_id, school_id)
        if other is not None:
            await session.execute(
                update(RollCallSession)
                .where(RollCallSession.id == session_id)
                .values(alert_event_id=other.id, is_drill=other.is_drill)
            )
            continue
        alert_id = await session.scalar(
            update(RollCallSession)
            .where(RollCallSession.id == session_id)
            .values(closed_at=at)
            .returning(RollCallSession.alert_event_id)
        )
        assert alert_id is not None
        closed.append((class_id, alert_id))
    return closed


async def react_school_alert(
    session: AsyncSession, alert: AlertEvent, at: dt.datetime, pushes: Pushes
) -> int:
    """Тривога з API для школи: класи, де зараз урок → перекличка + push з id уроку."""
    classes = await session.scalars(
        select(SchoolClass).where(SchoolClass.school_id == alert.school_id).order_by(SchoolClass.id)
    )
    reacted = 0
    for klass in classes:
        _, _, item = await school_service.current_lesson(session, klass, at)
        if item is None:
            continue
        await react_class(session, klass.id, alert, at, item.lesson_id, pushes)
        reacted += 1
    return reacted


async def react_class(
    session: AsyncSession,
    class_id: uuid.UUID,
    alert: AlertEvent,
    at: dt.datetime,
    lesson_id: uuid.UUID | None,
    pushes: Pushes,
) -> None:
    """Реакція класу, у якого йде урок під час тривоги: перекличка + push «тривога, відкрий
    урок» з id уроку (після commit)."""
    await open_rollcall(session, class_id, alert, at)
    pushes.add("alert", class_id, alert_id=alert.id, lesson_id=lesson_id)


async def react_lesson_starts(
    session: AsyncSession, window: dt.timedelta, now: dt.datetime | None = None
) -> dict[str, int]:
    """Урок почався, коли тривога вже йшла (beat-задача `alerts.lesson_starts`): класи під
    активною тривогою (з API — уся школа, ручна — лише її клас), у яких поточний урок почався
    за останні `window`, отримують ту саму реакцію, що й на початку тривоги (`react_class`).

    Клас, у якого вже є перекличка (відкрита чи закрита) однієї з тривог, що його покривають,
    пропускається: реакція на старті тривоги, попередній урок або попередній запуск задачі.
    Перевірка й реакція — під advisory lock класу, тож повтор чи паралельний запуск не дає
    другої переклички чи push. Справжня тривога має пріоритет над навчальною."""
    now = now or _now()
    alerts = list(
        await session.scalars(
            select(AlertEvent)
            .where(AlertEvent.ended_at.is_(None))
            .order_by(AlertEvent.is_drill, AlertEvent.started_at, AlertEvent.id)
        )
    )
    pushes = Pushes()
    reacted = 0
    if alerts:
        school_ids = {a.school_id for a in alerts if a.class_id is None}
        class_ids = {a.class_id for a in alerts if a.class_id is not None}
        classes = await session.scalars(
            select(SchoolClass)
            .where(or_(SchoolClass.school_id.in_(school_ids), SchoolClass.id.in_(class_ids)))
            .order_by(SchoolClass.id)
        )
        for klass in list(classes):
            covering = [
                a
                for a in alerts
                if a.class_id == klass.id or (a.class_id is None and a.school_id == klass.school_id)
            ]
            _, _, item = await school_service.current_lesson(session, klass, now)
            if item is None or not (now - window < item.starts_at_utc <= now):
                continue
            key = f"alert-lesson-start:{klass.id}"
            await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))
            done = await session.scalar(
                select(
                    exists().where(
                        RollCallSession.class_id == klass.id,
                        RollCallSession.alert_event_id.in_([a.id for a in covering]),
                    )
                )
            )
            if done:
                continue
            # Тривога могла закінчитися після першого читання. FOR SHARE: паралельний відбій
            # дочекається commit і закриє щойно відкриту перекличку.
            alert = await session.scalar(
                select(AlertEvent)
                .where(AlertEvent.id.in_([a.id for a in covering]), AlertEvent.ended_at.is_(None))
                .order_by(AlertEvent.is_drill, AlertEvent.started_at, AlertEvent.id)
                .limit(1)
                .with_for_update(read=True)
            )
            if alert is None:
                continue
            await react_class(session, klass.id, alert, now, item.lesson_id, pushes)
            reacted += 1
    await session.commit()
    await pushes.send()
    result = {"classes": reacted, "pushes": len(pushes.items)}
    if reacted:
        logger.info("Lessons started during an alert: %s", result)
    return result


async def _end_alerts(
    session: AsyncSession, alert_ids: list[uuid.UUID], at: dt.datetime, pushes: Pushes
) -> list[uuid.UUID]:
    """Відбій: ended_at лише там, де його ще немає (повтор нічого не робить)."""
    if not alert_ids:
        return []
    ended = list(
        await session.scalars(
            update(AlertEvent)
            .where(AlertEvent.id.in_(alert_ids), AlertEvent.ended_at.is_(None))
            .values(ended_at=at)
            .returning(AlertEvent.id)
        )
    )
    for class_id, alert_id in await _close_rollcalls(session, ended, at):
        pushes.add("all_clear", class_id, alert_id=alert_id)
    return ended


# ---------- опитування API тривог ----------


async def _record_attempt(
    session: AsyncSession, name: str, at: dt.datetime, error: str | None
) -> None:
    values: dict[str, Any] = {"last_attempt_at": at, "last_error": error}
    if error is None:
        values["last_success_at"] = at
    stmt = pg_insert(AlertSource).values(name=name, **values)
    await session.execute(stmt.on_conflict_do_update(index_elements=["name"], set_=values))


async def poll(
    session: AsyncSession, provider: AlertProvider, now: dt.datetime | None = None
) -> dict[str, int | str]:
    """Один цикл опитування. Стан-орієнтований: тривога, якої немає серед активних, —
    відбій (лише якщо відповідь повна: усі записи розібрано). Ідемпотентний: повторний
    запуск з тими самими даними нічого не змінює."""
    now = now or _now()
    try:
        response = await provider.active_alerts()
    except AlertProviderError as exc:
        logger.warning("Alert provider %s failed: %s", provider.name, exc.reason)
        await _record_attempt(session, provider.name, now, exc.reason)
        await session.commit()
        return {"error": exc.reason}

    active = response.alerts
    pushes = Pushes()
    started = reopened = 0
    regions = {a.region_code for a in active}
    schools: dict[str, list[uuid.UUID]] = defaultdict(list)
    if regions:
        for school_id, region in await session.execute(
            select(School.id, School.region_code)
            .where(School.region_code.in_(regions))
            .order_by(School.id)
        ):
            schools[region].append(school_id)

    for a in active:
        for school_id in schools[a.region_code]:
            new_id = await session.scalar(
                pg_insert(AlertEvent)
                .values(
                    id=uuid.uuid4(),
                    region_code=a.region_code,
                    school_id=school_id,
                    source="api",
                    external_id=a.external_id,
                    is_drill=False,
                    started_at=a.started_at,
                )
                .on_conflict_do_nothing(index_elements=_API_KEY, index_where=_API_KEY_WHERE)
                .returning(AlertEvent.id)
            )
            if new_id is None:
                # Тривога вже в журналі. Якщо її помилково закрили (API на мить її не
                # повернуло), а вона знову активна — відновлюємо й реагуємо ще раз.
                new_id = await session.scalar(
                    update(AlertEvent)
                    .where(
                        AlertEvent.source == "api",
                        AlertEvent.region_code == a.region_code,
                        AlertEvent.external_id == a.external_id,
                        AlertEvent.school_id == school_id,
                        AlertEvent.ended_at.is_not(None),
                    )
                    .values(ended_at=None)
                    .returning(AlertEvent.id)
                )
                if new_id is None:
                    continue
                reopened += 1
            else:
                started += 1
            alert = await session.get(AlertEvent, new_id, populate_existing=True)
            assert alert is not None
            await react_school_alert(session, alert, now, pushes)

    ended: list[uuid.UUID] = []
    if response.complete:
        active_keys = {(a.region_code, a.external_id) for a in active}
        open_rows = await session.execute(
            select(AlertEvent.id, AlertEvent.region_code, AlertEvent.external_id).where(
                AlertEvent.source == "api", AlertEvent.ended_at.is_(None)
            )
        )
        to_end = [r.id for r in open_rows if (r.region_code, r.external_id) not in active_keys]
        ended = await _end_alerts(session, to_end, now, pushes)
    else:
        # Невалідний запис міг бути активною тривогою: його відсутність — не відбій.
        logger.warning("Alert provider %s: incomplete response, ending skipped", provider.name)

    await _record_attempt(session, provider.name, now, None)
    await session.commit()
    await pushes.send()
    result = {
        "active": len(active),
        "started": started,
        "reopened": reopened,
        "ended": len(ended),
        "pushes": len(pushes.items),
    }
    logger.info("Alert poll: %s", result)
    return result


async def source_available(
    session: AsyncSession, settings: Settings, now: dt.datetime | None = None
) -> bool:
    """false, якщо опитування вимкнене або останній успіх давніший за ALERTS_SOURCE_STALE_S."""
    if not settings.alerts_polling_enabled:
        return False
    last = await session.scalar(
        select(AlertSource.last_success_at).where(AlertSource.name == SOURCE_NAME)
    )
    now = now or _now()
    return last is not None and now - last <= dt.timedelta(seconds=settings.alerts_source_stale_s)


# ---------- автозакриття забутих ручних тривог і перекличок ----------


async def _api_alert_active(session: AsyncSession, school_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    AlertEvent.source == "api",
                    AlertEvent.ended_at.is_(None),
                    AlertEvent.school_id == school_id,
                )
            )
        )
    )


async def auto_close_stale(
    session: AsyncSession, settings: Settings, now: dt.datetime | None = None
) -> dict[str, int]:
    """Вчитель забув натиснути відбій: ручна (зокрема навчальна) тривога, старша за
    ALERTS_MANUAL_MAX_HOURS, завершується як звичайний відбій (перекличка закривається, push
    `all_clear`). Ручна перекличка без тривоги такого віку закривається як вчителем (без push).
    Поки школу покриває тривога з API, нічого не чіпаємо: тривога реальна, закриється пізніше.
    Ідемпотентно: повтор чи паралельний запуск не закриває й не шле вдруге."""
    now = now or _now()
    before = now - dt.timedelta(hours=settings.alerts_manual_max_hours)
    stale = await session.execute(
        select(AlertEvent.id, AlertEvent.school_id)
        .where(
            AlertEvent.source == "manual",
            AlertEvent.ended_at.is_(None),
            AlertEvent.started_at < before,
        )
        .order_by(AlertEvent.started_at, AlertEvent.id)
    )
    to_end = [
        alert_id
        for alert_id, school_id in stale.all()
        if not await _api_alert_active(session, school_id)
    ]
    pushes = Pushes()
    ended = await _end_alerts(session, to_end, now, pushes)

    rollcalls = await session.execute(
        select(RollCallSession.id, RollCallSession.class_id, SchoolClass.school_id)
        .join(SchoolClass, SchoolClass.id == RollCallSession.class_id)
        .where(
            RollCallSession.alert_event_id.is_(None),
            RollCallSession.closed_at.is_(None),
            RollCallSession.opened_at < before,
        )
        .order_by(RollCallSession.id)
        .with_for_update(of=RollCallSession)
    )
    closed = 0
    for session_id, class_id, school_id in rollcalls.all():
        if await _covering_alert(session, class_id, school_id) is not None:
            continue
        await session.execute(
            update(RollCallSession)
            .where(RollCallSession.id == session_id, RollCallSession.closed_at.is_(None))
            .values(closed_at=now)
        )
        closed += 1
    await session.commit()
    await pushes.send()
    result = {"alerts": len(ended), "rollcalls": closed, "pushes": len(pushes.items)}
    if ended or closed:
        logger.info("Stale manual alerts and roll calls closed: %s", result)
    return result


# ---------- ручна тривога ----------


async def _staff_class(session: AsyncSession, user: User, class_id: uuid.UUID) -> SchoolClass:
    klass = await auth_service.get_class(session, class_id)
    if klass is None:
        raise AppError("NOT_FOUND", "Class not found", status_code=404)
    if user.role not in ("teacher", "admin") or not await auth_service.can_access_class(
        session, user, klass
    ):
        raise AppError("FORBIDDEN", "No access to this class", status_code=403)
    return klass


async def create_manual(
    session: AsyncSession, user: User, body: ManualAlertCreate
) -> tuple[AlertEvent, bool]:
    """Вчитель класу або адмін школи. Ідемпотентно за `id`: повтор не відкриває перекличку
    й не шле push вдруге. Перекличка відкривається навіть без уроку зараз (вчитель натиснув
    кнопку свідомо); id уроку в push — якщо урок іде."""
    klass = await _staff_class(session, user, body.class_id)
    school = await session.get(School, klass.school_id)
    assert school is not None
    now = _now()
    alert, created = await insert_or_get(
        session,
        AlertEvent,
        {
            "id": body.id,
            "region_code": school.region_code,
            "school_id": school.id,
            "class_id": klass.id,
            "source": "manual",
            "external_id": None,
            "is_drill": body.is_drill,
            "started_at": now,
            "created_by": user.id,
        },
        compare=["class_id", "source", "is_drill"],
    )
    if not created:
        return alert, False
    pushes = Pushes()
    _, _, item = await school_service.current_lesson(session, klass, now)
    await open_rollcall(session, klass.id, alert, now, opened_by=user.id)
    pushes.add("alert", klass.id, alert_id=alert.id, lesson_id=item.lesson_id if item else None)
    await session.commit()
    await pushes.send()
    return alert, True


async def end_manual(session: AsyncSession, user: User, alert_id: uuid.UUID) -> AlertEvent:
    """Відбій ручної тривоги. Ідемпотентно: уже завершена повертається як є."""
    alert = await session.get(AlertEvent, alert_id)
    if alert is None:
        raise AppError("NOT_FOUND", "Alert not found", status_code=404)
    if alert.source != "manual" or alert.class_id is None:
        # Права перевіряємо й тут, щоб не розкривати чужі тривоги.
        if user.role != "admin" or alert.school_id != user.school_id:
            raise AppError("FORBIDDEN", "No access to this alert", status_code=403)
        raise AppError(
            "ALERT_NOT_MANUAL", "Alerts from the alert API end only via the API", status_code=409
        )
    await _staff_class(session, user, alert.class_id)
    pushes = Pushes()
    await _end_alerts(session, [alert.id], _now(), pushes)
    await session.commit()
    await pushes.send()
    await session.refresh(alert)
    return alert


# ---------- читання ----------


async def _scope(session: AsyncSession, user: User) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    """(школи, класи), тривоги яких бачить користувач."""
    if user.role == "admin":
        return ({user.school_id} if user.school_id else set()), set()
    if user.role == "parent":
        members = select(ParentChild.child_id).where(ParentChild.parent_id == user.id)
        cond = and_(ClassMembership.user_id.in_(members), ClassMembership.member_role == "student")
    else:
        cond = and_(ClassMembership.user_id == user.id, ClassMembership.member_role == user.role)
    rows = await session.execute(
        select(SchoolClass.id, SchoolClass.school_id)
        .join(ClassMembership, ClassMembership.class_id == SchoolClass.id)
        .where(cond)
    )
    classes, schools = set(), set()
    for class_id, school_id in rows:
        classes.add(class_id)
        schools.add(school_id)
    return schools, classes


async def active_alerts(session: AsyncSession, user: User) -> list[AlertEvent]:
    """Тривоги шкіл користувача (з API) і ручні тривоги його класів, без відбою.
    Адмін бачить усі тривоги школи, зокрема ручні тривоги будь-якого класу."""
    schools, classes = await _scope(session, user)
    if not schools and not classes:
        return []
    if user.role == "admin":
        visible = AlertEvent.school_id.in_(schools)
    else:
        visible = or_(
            and_(AlertEvent.class_id.is_(None), AlertEvent.school_id.in_(schools)),
            AlertEvent.class_id.in_(classes),
        )
    rows = await session.scalars(
        select(AlertEvent)
        .where(AlertEvent.ended_at.is_(None), visible)
        .order_by(AlertEvent.started_at.desc(), AlertEvent.id)
    )
    return list(rows)


async def journal(
    session: AsyncSession,
    admin: User,
    date_from: dt.date | None,
    date_to: dt.date | None,
    limit: int,
    offset: int,
) -> list[AlertEvent]:
    """Журнал тривог школи адміна; `from`/`to` — дати за київським часом, включно."""
    if admin.school_id is None:
        return []
    tz = ZoneInfo(DEFAULT_TZ)
    query = select(AlertEvent).where(AlertEvent.school_id == admin.school_id)
    if date_from is not None:
        query = query.where(
            AlertEvent.started_at >= dt.datetime.combine(date_from, dt.time(), tzinfo=tz)
        )
    if date_to is not None:
        end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time(), tzinfo=tz)
        query = query.where(AlertEvent.started_at < end)
    rows = await session.scalars(
        query.order_by(AlertEvent.started_at.desc(), AlertEvent.id).limit(limit).offset(offset)
    )
    return list(rows)
