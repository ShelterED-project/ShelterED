import datetime as dt
import uuid

import pytest
from conftest import Factory
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_link_code
from app.models.alerts import AlertEvent
from app.models.lessons import Lesson, Module, Subject, Test
from app.models.rollcall import RollCallSession, RollCallStatus
from app.models.school import School, SchoolClass, User
from app.models.sync import Attempt, ModuleProgress, SyncEvent

pytestmark = pytest.mark.anyio

NOW = dt.datetime(2026, 11, 1, 10, 0, tzinfo=dt.UTC)


async def make_graph(session: AsyncSession) -> dict:
    """Школа, клас, вчитель, учень, урок з модулем і тестом."""
    school = await Factory(session).school()
    klass = SchoolClass(
        school_id=school.id,
        name="7-А",
        grade=7,
        academic_year="2026/2027",
        join_code=new_link_code(),
    )
    teacher = User(role="teacher", display_name="Олена", school_id=school.id, email="t@example.com")
    student = User(role="student", display_name="Іван", last_name="Петренко", school_id=school.id)
    subject = Subject(name="Математика")
    session.add_all([klass, teacher, student, subject])
    await session.flush()
    lesson = Lesson(
        subject_id=subject.id,
        author_id=teacher.id,
        title="Дроби",
        shelter_part="...",
        main_part="...",
    )
    session.add(lesson)
    await session.flush()
    module = Module(lesson_id=lesson.id, part="shelter", position=1, title="М1", duration_min=4)
    test = Test(lesson_id=lesson.id, title="Тест")
    session.add_all([module, test])
    await session.flush()
    return {"school": school, "klass": klass, "student": student, "module": module, "test": test}


def event(user_id: uuid.UUID, event_type: str, event_id: uuid.UUID | None = None) -> SyncEvent:
    return SyncEvent(
        client_event_id=event_id or uuid.uuid4(),
        type=event_type,
        user_id=user_id,
        device_id=uuid.uuid4(),
        occurred_at=NOW,
        payload={},
        status="accepted",
    )


async def test_minimal_graph_and_defaults(db_session: AsyncSession) -> None:
    g = await make_graph(db_session)
    assert g["school"].timezone == "Europe/Kyiv"
    lesson = (await db_session.execute(select(Lesson))).scalars().one()
    assert lesson.status == "draft"
    assert lesson.version == 1


async def test_invalid_role_rejected(db_session: AsyncSession) -> None:
    db_session.add(User(role="superuser", display_name="X"))
    with pytest.raises(IntegrityError, match="ck_app_user_role"):
        await db_session.flush()


async def test_student_cannot_have_email(db_session: AsyncSession) -> None:
    db_session.add(User(role="student", display_name="Іван", email="kid@example.com"))
    with pytest.raises(IntegrityError, match="ck_app_user_student_no_credentials"):
        await db_session.flush()


async def test_duplicate_client_event_id_rejected(db_session: AsyncSession) -> None:
    g = await make_graph(db_session)
    event_id = uuid.uuid4()
    db_session.add(event(g["student"].id, "module_progress", event_id))
    await db_session.flush()
    db_session.add(event(g["student"].id, "module_progress", event_id))
    with pytest.raises(IntegrityError, match="pk_sync_event"):
        await db_session.flush()


async def test_on_conflict_do_nothing_inserts_once(db_session: AsyncSession) -> None:
    g = await make_graph(db_session)
    values = {
        "client_event_id": uuid.uuid4(),
        "type": "rollcall_status",
        "user_id": g["student"].id,
        "device_id": uuid.uuid4(),
        "occurred_at": NOW,
        "payload": {},
        "status": "accepted",
    }
    stmt = insert(SyncEvent).values(**values).on_conflict_do_nothing()
    first = await db_session.execute(stmt)
    second = await db_session.execute(stmt)
    assert (first.rowcount, second.rowcount) == (1, 0)
    count = await db_session.scalar(select(func.count()).select_from(SyncEvent))
    assert count == 1


async def test_only_one_credited_attempt_per_test(db_session: AsyncSession) -> None:
    g = await make_graph(db_session)
    events = [event(g["student"].id, "test_attempt") for _ in range(2)]
    db_session.add_all(events)
    await db_session.flush()

    def attempt(e: SyncEvent, credit: str) -> Attempt:
        return Attempt(
            client_event_id=e.client_event_id,
            student_id=g["student"].id,
            test_id=g["test"].id,
            answers={},
            completed_at_client=NOW,
            credit_status=credit,
        )

    db_session.add(attempt(events[0], "credited"))
    await db_session.flush()
    db_session.add(attempt(events[1], "credited"))
    with pytest.raises(IntegrityError, match="uq_attempt_student_id_test_id_credited"):
        await db_session.flush()


async def test_deleting_student_cascades_personal_data(db_session: AsyncSession) -> None:
    g = await make_graph(db_session)
    student_id = g["student"].id
    ev_attempt = event(student_id, "test_attempt")
    ev_progress = event(student_id, "module_progress")
    ev_roll = event(student_id, "rollcall_status")
    db_session.add_all([ev_attempt, ev_progress, ev_roll])
    session = RollCallSession(class_id=g["klass"].id, opened_at=NOW)
    db_session.add(session)
    await db_session.flush()
    db_session.add_all(
        [
            Attempt(
                client_event_id=ev_attempt.client_event_id,
                student_id=student_id,
                test_id=g["test"].id,
                answers={},
                completed_at_client=NOW,
                credit_status="credited",
            ),
            ModuleProgress(
                student_id=student_id,
                module_id=g["module"].id,
                progress_pct=100,
                last_event_id=ev_progress.client_event_id,
            ),
            RollCallStatus(
                session_id=session.id,
                student_id=student_id,
                status="in_shelter",
                occurred_at=NOW,
                received_at=NOW,
                last_event_id=ev_roll.client_event_id,
            ),
        ]
    )
    await db_session.flush()

    await db_session.execute(delete(User).where(User.id == student_id))

    for model in (Attempt, ModuleProgress, RollCallStatus, SyncEvent):
        count = await db_session.scalar(select(func.count()).select_from(model))
        assert count == 0, model.__name__


async def test_clock_skew_fits_beyond_int32(db_session: AsyncSession) -> None:
    g = await make_graph(db_session)
    e = event(g["student"].id, "module_progress")
    e.clock_skew_ms = 3_000_000_000  # ~35 діб; не влізає в integer
    db_session.add(e)
    await db_session.flush()
    stored = await db_session.scalar(select(SyncEvent.clock_skew_ms))
    assert stored == 3_000_000_000


def alert(school_id: uuid.UUID | None, external_id: str | None = "a-1", source: str = "api"):
    return AlertEvent(
        region_code="kyiv",
        school_id=school_id,
        source=source,
        external_id=external_id,
        started_at=NOW,
    )


async def test_alert_duplicate_with_null_school_rejected(db_session: AsyncSession) -> None:
    db_session.add(alert(None))
    await db_session.flush()
    db_session.add(alert(None))
    with pytest.raises(IntegrityError, match="uq_alert_event_source_external_school"):
        await db_session.flush()


async def test_alert_duplicate_for_school_rejected_but_other_school_ok(
    db_session: AsyncSession,
) -> None:
    school_a, school_b = School(name="A", region_code="kyiv"), School(name="B", region_code="kyiv")
    db_session.add_all([school_a, school_b])
    await db_session.flush()
    db_session.add_all([alert(school_a.id), alert(school_b.id), alert(None)])
    await db_session.flush()
    db_session.add(alert(school_a.id))
    with pytest.raises(IntegrityError, match="uq_alert_event_source_external_school"):
        await db_session.flush()


async def test_manual_alerts_without_external_id_may_repeat(db_session: AsyncSession) -> None:
    school = School(name="A", region_code="kyiv")
    db_session.add(school)
    await db_session.flush()
    db_session.add_all([alert(school.id, None, "manual"), alert(school.id, None, "manual")])
    await db_session.flush()
