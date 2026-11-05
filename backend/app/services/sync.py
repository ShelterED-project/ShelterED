"""Синхронізація подій з пристроїв (B9, контракт — docs/sync-protocol.md v1).

Прийом пакета: кожна подія — в окремій транзакції (commit після кожної), тож збій посеред
пакета не губить уже оброблені події, а повтор пакета дає для них `duplicate`. Ідемпотентність
тримає PK `sync_event.client_event_id` + `INSERT ... ON CONFLICT DO NOTHING`: паралельний
повтор чекає на транзакцію-переможця й отримує збережений результат.

Застосування (лише для прийнятих подій), правила конфліктів — розділ 5 протоколу:
- `module_progress` — максимум `progress_pct` (і найраніший `completed_at`);
- `test_attempt` — зараховується перша завершена спроба (за `completed_at` пристрою), решта
  зберігаються з `not_credited_repeat`; оцінює сервер за `answer_key`;
- `rollcall_status` — перемагає найпізніший `occurred_at`;
- `survey_answer` — лише запис у `sync_event` (окреме сховище — B13.4).

Стрічка змін: `change_seq`/`change_xid` ставить тригер (міграція 827ed8465b1b). Курсор —
пара (xid, seq): віддаються лише рядки транзакцій, старших за найстарішу ще активну
(`xid < pg_snapshot_xmin(pg_current_snapshot())`). Будь-яка транзакція, що закомітиться
пізніше, має xid >= цього xmin, тобто стоїть у стрічці після курсора — пропусків немає.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, exists, func, literal, or_, select, text, tuple_, union_all, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.lessons import Module, Question, Test
from app.models.packs import KnowledgePack, KnowledgePackLesson
from app.models.rollcall import RollCallSession, RollCallStatus
from app.models.school import ClassMembership, LessonAssignment, ScheduleSlot, User
from app.models.sync import Attempt, ModuleProgress, SyncEvent
from app.schemas.sync import (
    PAYLOAD_MODELS,
    AttemptResultChange,
    ModuleProgressChange,
    ModuleProgressPayload,
    RollCallStatusChange,
    RollCallStatusPayload,
    SyncChangesOut,
    SyncEventIn,
    SyncEventResult,
    SyncEventsRequest,
    SyncEventsResponse,
    TestAttemptPayload,
)

logger = logging.getLogger(__name__)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Rejected(Exception):
    """Подію не прийнято з кодом причини з розділу 7 протоколу."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Batch:
    """Спільне для всіх подій пакета: автор, час сервера, зсув годинника. Лише значення, не
    ORM-об'єкти: rollback після збою події робить їх простроченими."""

    user_id: uuid.UUID
    received_at: dt.datetime
    clock_skew_ms: int
    suspicious_skew: bool
    threshold: dt.timedelta


def _result(event_id: uuid.UUID, status: str, reason: str | None = None) -> SyncEventResult:
    return SyncEventResult(client_event_id=event_id, status=status, reason=reason)  # type: ignore[arg-type]


# ---------- доступ і застосування ----------


def _student_classes(student_id: uuid.UUID):
    return select(ClassMembership.class_id).where(
        ClassMembership.user_id == student_id, ClassMembership.member_role == "student"
    )


async def _student_has_lesson(
    session: AsyncSession, student_id: uuid.UUID, lesson_id: uuid.UUID
) -> bool:
    """Урок був у пакеті класу учня або прив'язаний до розкладу його класу. Пакет рахується
    теж: зміна розкладу після того, як учень пройшов урок офлайн, не має губити прогрес."""
    classes = _student_classes(student_id)
    in_pack = (
        select(KnowledgePackLesson.lesson_id)
        .join(KnowledgePack, KnowledgePack.id == KnowledgePackLesson.pack_id)
        .where(KnowledgePack.class_id.in_(classes), KnowledgePackLesson.lesson_id == lesson_id)
    )
    assigned = (
        select(LessonAssignment.lesson_id)
        .join(ScheduleSlot, ScheduleSlot.id == LessonAssignment.slot_id)
        .where(ScheduleSlot.class_id.in_(classes), LessonAssignment.lesson_id == lesson_id)
    )
    return bool(await session.scalar(select(or_(exists(in_pack), exists(assigned)))))


async def _check_lesson_access(
    session: AsyncSession, student_id: uuid.UUID, lesson_id: uuid.UUID | None
) -> None:
    if lesson_id is None:
        raise Rejected("unknown_entity")
    if not await _student_has_lesson(session, student_id, lesson_id):
        raise Rejected("forbidden")


async def _check_module_progress(
    session: AsyncSession, batch: Batch, payload: ModuleProgressPayload
) -> None:
    lesson_id = await session.scalar(select(Module.lesson_id).where(Module.id == payload.module_id))
    await _check_lesson_access(session, batch.user_id, lesson_id)


async def _apply_module_progress(
    session: AsyncSession, batch: Batch, event_id: uuid.UUID, payload: ModuleProgressPayload
) -> None:
    stmt = pg_insert(ModuleProgress).values(
        student_id=batch.user_id,
        module_id=payload.module_id,
        progress_pct=payload.progress_pct,
        completed_at_client=payload.completed_at,
        last_event_id=event_id,
    )
    new = stmt.excluded
    cur = ModuleProgress.__table__.c
    # Рядок змінюється (і потрапляє в стрічку змін) лише якщо подія щось покращує.
    improves = or_(
        new.progress_pct > cur.progress_pct,
        and_(
            new.completed_at_client.is_not(None),
            or_(
                cur.completed_at_client.is_(None),
                new.completed_at_client < cur.completed_at_client,
            ),
        ),
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["student_id", "module_id"],
            set_={
                "progress_pct": func.greatest(cur.progress_pct, new.progress_pct),
                # LEAST ігнорує NULL: найраніше відоме завершення.
                "completed_at_client": func.least(cur.completed_at_client, new.completed_at_client),
                "last_event_id": new.last_event_id,
            },
            where=improves,
        )
    )


async def _check_test_attempt(
    session: AsyncSession, batch: Batch, payload: TestAttemptPayload
) -> None:
    lesson_id = await session.scalar(select(Test.lesson_id).where(Test.id == payload.test_id))
    await _check_lesson_access(session, batch.user_id, lesson_id)


async def grade(
    session: AsyncSession, test_id: uuid.UUID, answers: dict[Any, list[str]]
) -> Decimal | None:
    """Відсоток балів (0..100, 2 знаки): питання зараховане, якщо множина обраних варіантів
    дорівнює ключу. Відповіді на питання не з цього тесту ігноруються. Тест без питань — None."""
    questions = await session.execute(
        select(Question.id, Question.answer_key, Question.points).where(Question.test_id == test_id)
    )
    total = earned = 0
    for qid, key, points in questions:
        total += points
        if set(answers.get(qid, [])) == set(key or []) and key:
            earned += points
    if total == 0:
        return None
    return (Decimal(earned * 100) / Decimal(total)).quantize(Decimal("0.01"))


async def _apply_test_attempt(
    session: AsyncSession,
    batch: Batch,
    event_id: uuid.UUID,
    payload: TestAttemptPayload,
    suspicious: bool,
) -> None:
    student_id = batch.user_id
    # Паралельні спроби того самого тесту зараховуємо по черзі (до кінця транзакції події).
    await session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(f"attempt:{student_id}:{payload.test_id}", 0)
            )
        )
    )
    credited = (
        await session.execute(
            select(Attempt.id, Attempt.completed_at_client, Attempt.client_event_id).where(
                Attempt.student_id == student_id,
                Attempt.test_id == payload.test_id,
                Attempt.credit_status == "credited",
            )
        )
    ).first()
    # Перша завершена спроба за часом пристрою (рівність — менший client_event_id), незалежно
    # від порядку надходження: офлайн-спроба з іншого пристрою може прийти пізніше.
    mine = (payload.completed_at, event_id)
    if credited is None:
        status = "credited"
    elif mine < (credited.completed_at_client, credited.client_event_id):
        await session.execute(
            update(Attempt)
            .where(Attempt.id == credited.id)
            .values(credit_status="not_credited_repeat")
        )
        status = "credited"
    else:
        status = "not_credited_repeat"
    # Вікно тесту (B11, P1) ще не застосовується: `not_credited_late` поки не ставиться.
    session.add(
        Attempt(
            client_event_id=event_id,
            student_id=student_id,
            test_id=payload.test_id,
            answers={str(k): v for k, v in payload.answers.items()},
            completed_at_client=payload.completed_at,
            received_at=batch.received_at,
            score=await grade(session, payload.test_id, payload.answers),
            credit_status=status,
            is_suspicious=suspicious,
        )
    )
    await session.flush()


async def _check_rollcall(
    session: AsyncSession, batch: Batch, occurred_at: dt.datetime, payload: RollCallStatusPayload
) -> None:
    rc = await session.get(RollCallSession, payload.session_id)
    if rc is None:
        raise Rejected("unknown_entity")
    member = await session.scalar(
        select(ClassMembership.user_id).where(
            ClassMembership.class_id == rc.class_id,
            ClassMembership.user_id == batch.user_id,
            ClassMembership.member_role == "student",
        )
    )
    if member is None:
        raise Rejected("forbidden")
    if rc.closed_at is not None and occurred_at > rc.closed_at:
        raise Rejected("session_closed")


async def _apply_rollcall(
    session: AsyncSession,
    batch: Batch,
    event_id: uuid.UUID,
    occurred_at: dt.datetime,
    payload: RollCallStatusPayload,
) -> None:
    stmt = pg_insert(RollCallStatus).values(
        session_id=payload.session_id,
        student_id=batch.user_id,
        status=payload.status,
        occurred_at=occurred_at,
        received_at=batch.received_at,
        last_event_id=event_id,
    )
    new = stmt.excluded
    cur = RollCallStatus.__table__.c
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["session_id", "student_id"],
            set_={
                "status": new.status,
                "occurred_at": new.occurred_at,
                "received_at": new.received_at,
                "last_event_id": new.last_event_id,
            },
            # Найпізніший occurred_at; рівний час — більший id події (детерміновано).
            where=tuple_(new.occurred_at, new.last_event_id)
            > tuple_(cur.occurred_at, cur.last_event_id),
        )
    )


# ---------- прийом пакета ----------


async def _stored_result(
    session: AsyncSession, batch: Batch, event_id: uuid.UUID
) -> SyncEventResult | None:
    """Результат для вже записаної події: прийнята → `duplicate`, відхилена → та сама причина.
    Чужий id (інший автор) — `forbidden`, нічого не розкриваючи й не перезаписуючи."""
    row = (
        await session.execute(
            select(SyncEvent.user_id, SyncEvent.status, SyncEvent.reject_reason).where(
                SyncEvent.client_event_id == event_id
            )
        )
    ).first()
    if row is None:
        return None
    if row.user_id != batch.user_id:
        return _result(event_id, "rejected", "forbidden")
    if row.status == "rejected":
        return _result(event_id, "rejected", row.reject_reason)
    return _result(event_id, "duplicate")


async def _process_event(
    session: AsyncSession, batch: Batch, event: SyncEventIn
) -> SyncEventResult:
    stored = await _stored_result(session, batch, event.client_event_id)
    if stored is not None:
        return stored
    model = PAYLOAD_MODELS.get(event.type)
    if model is None:
        # CHECK у БД не дає записати невідомий тип; результат детермінований і без запису.
        return _result(event.client_event_id, "rejected", "unknown_type")

    occurred_at = event.occurred_at.astimezone(dt.UTC)
    suspicious = batch.suspicious_skew or occurred_at > batch.received_at + batch.threshold
    reason: str | None = None
    payload: BaseModel | None = None
    try:
        payload = model.model_validate(event.payload)
    except ValidationError:
        reason = "invalid_payload"
    try:
        if isinstance(payload, ModuleProgressPayload):
            await _check_module_progress(session, batch, payload)
        elif isinstance(payload, TestAttemptPayload):
            await _check_test_attempt(session, batch, payload)
        elif isinstance(payload, RollCallStatusPayload):
            await _check_rollcall(session, batch, occurred_at, payload)
    except Rejected as exc:
        reason = exc.reason

    inserted = await session.scalar(
        pg_insert(SyncEvent)
        .values(
            client_event_id=event.client_event_id,
            type=event.type,
            user_id=batch.user_id,
            device_id=event.device_id,
            occurred_at=occurred_at,
            received_at=batch.received_at,
            clock_skew_ms=batch.clock_skew_ms,
            is_suspicious=suspicious,
            source="online",
            relayed_by=None,
            payload=event.payload,
            status="rejected" if reason else "accepted",
            reject_reason=reason,
        )
        .on_conflict_do_nothing(index_elements=["client_event_id"])
        .returning(SyncEvent.client_event_id)
    )
    if inserted is None:
        # Паралельний запит з тією самою подією встиг першим (ми дочекалися його commit).
        stored = await _stored_result(session, batch, event.client_event_id)
        assert stored is not None
        return stored
    if reason:
        return _result(event.client_event_id, "rejected", reason)

    if isinstance(payload, ModuleProgressPayload):
        await _apply_module_progress(session, batch, event.client_event_id, payload)
    elif isinstance(payload, TestAttemptPayload):
        await _apply_test_attempt(session, batch, event.client_event_id, payload, suspicious)
    elif isinstance(payload, RollCallStatusPayload):
        await _apply_rollcall(session, batch, event.client_event_id, occurred_at, payload)
    return _result(event.client_event_id, "accepted")


async def receive_events(
    session: AsyncSession,
    user: User,
    body: SyncEventsRequest,
    settings: Settings,
    now: dt.datetime | None = None,
) -> SyncEventsResponse:
    """`POST /sync/events`. Результати — у порядку подій у запиті; обробка — за `occurred_at`."""
    if user.role != "student":
        # QR-ретрансляція вчителем (B10): у конверті немає підписаного запису учня, тож
        # автора події визначити не можна. 501, а не `rejected`: клієнт лишить події в outbox.
        raise AppError("NOT_IMPLEMENTED", "QR relay of student events is not implemented yet", 501)
    received_at = now or _now()
    threshold = dt.timedelta(seconds=settings.sync_suspicious_skew_s)
    skew = received_at - body.sent_at
    batch = Batch(
        user_id=user.id,
        received_at=received_at,
        clock_skew_ms=int(skew / dt.timedelta(milliseconds=1)),
        suspicious_skew=abs(skew) > threshold,
        threshold=threshold,
    )

    results: list[SyncEventResult | None] = [None] * len(body.events)
    first: dict[uuid.UUID, int] = {}
    for i, event in enumerate(body.events):
        if event.client_event_id in first:
            results[i] = _result(event.client_event_id, "duplicate")
        else:
            first[event.client_event_id] = i
    order = sorted(first.values(), key=lambda i: (body.events[i].occurred_at, i))

    failed = 0
    for i in order:
        event = body.events[i]
        try:
            results[i] = await _process_event(session, batch, event)
            await session.commit()
        except Exception:
            # Інфраструктурна помилка (не правило протоколу): лише ця подія відкочується,
            # решта пакета обробляється; відповідь 500 — клієнт повторить пакет і отримає
            # `duplicate` для вже записаних подій. Payload у лог не пишемо.
            await session.rollback()
            failed += 1
            logger.exception("Sync event processing failed (type=%s)", event.type)
    if failed:
        raise AppError(
            "INTERNAL_ERROR",
            "Some events were not processed; retry the batch",
            500,
            details={"failed": failed},
        )

    final = [r for r in results if r is not None]
    counts = {s: sum(r.status == s for r in final) for s in ("accepted", "duplicate", "rejected")}
    logger.info("Sync batch: %d events, %s, skew_ms=%d", len(final), counts, batch.clock_skew_ms)
    return SyncEventsResponse(results=final, server_time=_now())


# ---------- стрічка змін ----------


def _bad_cursor() -> AppError:
    return AppError("INVALID_CURSOR", "Invalid sync cursor", status_code=422)


def parse_cursor(cursor: str | None) -> tuple[int, int]:
    """Курсор `"<xid>.<seq>"` (для клієнта непрозорий). Без курсора — з початку."""
    if not cursor:
        return (0, 0)
    xid, sep, seq = cursor.partition(".")
    if not sep or not xid.isdigit() or not seq.isdigit():
        raise _bad_cursor()
    return (int(xid), int(seq))


async def changes(
    session: AsyncSession, student: User, cursor: str | None, limit: int
) -> SyncChangesOut:
    """`GET /sync/changes`: актуальний стан змінених рядків учня після курсора, у порядку
    (change_xid, change_seq), лише з точно закомічених транзакцій."""
    after = parse_cursor(cursor)
    a, m, r = Attempt.__table__.c, ModuleProgress.__table__.c, RollCallStatus.__table__.c
    null_uuid = literal(None).cast(a.test_id.type)
    null_ts = literal(None).cast(r.occurred_at.type)
    null_text = literal(None).cast(r.status.type)

    def part(kind, c, cols):
        return select(
            literal(kind).label("kind"),
            c.change_xid.label("xid"),
            c.change_seq.label("seq"),
            *cols,
        ).where(
            c.student_id == student.id,
            tuple_(c.change_xid, c.change_seq) > tuple_(literal(after[0]), literal(after[1])),
            c.change_xid < text("pg_snapshot_xmin(pg_current_snapshot())::text::bigint"),
        )

    query = union_all(
        part(
            "attempt_result",
            a,
            [
                a.client_event_id.label("ref_id"),
                a.test_id.label("entity_id"),
                a.credit_status.label("state"),
                a.score.label("score"),
                a.is_suspicious.label("flag"),
                null_ts.label("at"),
                literal(None).cast(m.progress_pct.type).label("pct"),
            ],
        ),
        part(
            "module_progress",
            m,
            [
                null_uuid.label("ref_id"),
                m.module_id.label("entity_id"),
                null_text.label("state"),
                literal(None).cast(a.score.type).label("score"),
                literal(None).cast(a.is_suspicious.type).label("flag"),
                m.completed_at_client.label("at"),
                m.progress_pct.label("pct"),
            ],
        ),
        part(
            "rollcall_status",
            r,
            [
                null_uuid.label("ref_id"),
                r.session_id.label("entity_id"),
                r.status.label("state"),
                literal(None).cast(a.score.type).label("score"),
                literal(None).cast(a.is_suspicious.type).label("flag"),
                r.occurred_at.label("at"),
                literal(None).cast(m.progress_pct.type).label("pct"),
            ],
        ),
    ).subquery()
    rows = (
        await session.execute(select(query).order_by(query.c.xid, query.c.seq).limit(limit + 1))
    ).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items: list[Any] = []
    for row in rows:
        if row.kind == "attempt_result":
            items.append(
                AttemptResultChange(
                    kind="attempt_result",
                    client_event_id=row.ref_id,
                    test_id=row.entity_id,
                    credit_status=row.state,
                    score=None if row.score is None else float(row.score),
                    is_suspicious=row.flag,
                )
            )
        elif row.kind == "module_progress":
            items.append(
                ModuleProgressChange(
                    kind="module_progress",
                    module_id=row.entity_id,
                    progress_pct=row.pct,
                    completed_at=row.at,
                )
            )
        else:
            items.append(
                RollCallStatusChange(
                    kind="rollcall_status",
                    session_id=row.entity_id,
                    status=row.state,
                    occurred_at=row.at,
                )
            )
    last = (rows[-1].xid, rows[-1].seq) if rows else after
    return SyncChangesOut(changes=items, next_cursor=f"{last[0]}.{last[1]}", has_more=has_more)
