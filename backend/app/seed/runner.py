"""Демо-дані: `python -m app.cli seed` (B2.7).

Ідемпотентно: id — uuid5 від фіксованого простору імен, рядки вставляються як upsert (оновлення
лише тоді, коли дані справді змінилися), тож повторний запуск того самого дня нічого не змінює.
Розклад і прив'язки уроків рахуються від «сьогодні» (поточний і наступний тиждень), пакети
«Рюкзака» перезбираються на 7 днів. Облікові дані задаються лише при створенні акаунта.
"""

import datetime as dt
import secrets
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_secret_async, verify_secret_async
from app.models.alerts import AlertEvent
from app.models.lessons import Card, Lesson, Module, Question, Subject, Test
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
from app.seed import content as c
from app.services import packs as packs_service
from app.services.auth import name_key, revoke_all_sessions
from app.services.lessons import publish_problems

# Простір імен демо-даних: однакові ключі → однакові id при кожному запуску.
NAMESPACE = uuid.UUID("5e1d0a7a-2b6f-4c1e-9a43-0d3f5e8c7b21")
OPTION_IDS = "abcdefghij"


def sid(*parts: object) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, "/".join(str(p) for p in parts))


class SeedRefused(RuntimeError):
    """Сід заборонено в цьому оточенні."""


@dataclass
class SeedResult:
    school_id: uuid.UUID
    join_codes: dict[str, str]
    adult_emails: list[str]
    # Згенерований пароль дорослих (друкується один раз); None — пароль не змінювався
    # або взятий із SEED_PASSWORD.
    generated_password: str | None
    passwords_set: bool
    lessons: int
    packs_built: int
    problems: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


async def _upsert(
    session: AsyncSession,
    model: type,
    rows: list[dict[str, Any]],
    keys: Iterable[str] = ("id",),
    insert_only: Iterable[str] = (),
) -> None:
    """INSERT ... ON CONFLICT DO UPDATE лише змінених рядків (без змін — без запису)."""
    if not rows:
        return
    keys, insert_only = list(keys), set(insert_only)
    table = model.__table__  # type: ignore[attr-defined]
    stmt = pg_insert(model).values(rows)
    cols = [col for col in rows[0] if col not in keys and col not in insert_only]
    if not cols:
        await session.execute(stmt.on_conflict_do_nothing(index_elements=keys))
        return
    set_: dict[str, Any] = {col: stmt.excluded[col] for col in cols}
    if "updated_at" in table.c:
        set_["updated_at"] = func.now()
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=keys,
            set_=set_,
            where=or_(*(table.c[col].is_distinct_from(stmt.excluded[col]) for col in cols)),
        )
    )


async def _insert_once(
    session: AsyncSession, model: type, rows: list[dict[str, Any]], keys: Iterable[str] = ("id",)
) -> None:
    """Історичні записи (тривога, перекличка, події): створюються один раз і не оновлюються."""
    if rows:
        await session.execute(
            pg_insert(model).values(rows).on_conflict_do_nothing(index_elements=list(keys))
        )


def _time(value: str) -> dt.time:
    return dt.time.fromisoformat(value)


def academic_year_start(today: dt.date) -> dt.date:
    return dt.date(today.year if today.month >= 9 else today.year - 1, 9, 1)


def previous_school_day(today: dt.date) -> dt.date:
    day = today - dt.timedelta(days=1)
    while day.isoweekday() > 5:
        day -= dt.timedelta(days=1)
    return day


def subject_occurrence(week: Mapping[int, Sequence[str]], day: dt.date, n: int) -> int:
    """Порядковий номер уроку предмета слота (`day`, `n`) у безперервній нумерації тижнів:
    функція лише дати й розкладу, тож та сама дата завжди дає той самий урок, хоч би коли
    запускався seed (а уроки предмета по черзі змінюються від уроку до уроку й між тижнями).
    Тижні — від понеділка (`toordinal() == 1` — понеділок), без скидання на новий рік."""
    subject = week[day.isoweekday()][n]
    per_week = sum(day_subjects.count(subject) for day_subjects in week.values())
    earlier = sum(week.get(wd, []).count(subject) for wd in range(1, day.isoweekday()))
    earlier += week[day.isoweekday()][:n].count(subject)
    return (day.toordinal() - 1) // 7 * per_week + earlier


async def _adult_users(
    session: AsyncSession, adults: list[dict[str, Any]], password: str | None
) -> tuple[str | None, bool]:
    """Дорослі акаунти. Профіль (ім'я, email) оновлюється завжди, пароль — так:
    SEED_PASSWORD застосовується до всіх, у кого він інший; без нього, якщо всі акаунти вже є,
    паролі не чіпаємо, інакше генеруємо один пароль для всіх. Повертає (згенерований пароль,
    чи встановлювались паролі)."""
    ids = [a["id"] for a in adults]
    existing = dict(
        (await session.execute(select(User.id, User.password_hash).where(User.id.in_(ids)))).all()
    )
    generated = None
    if password is None and len(existing) < len(ids):
        password = generated = secrets.token_urlsafe(9)
    if password is None:
        await _upsert(session, User, adults)
        return None, False
    hashed = await hash_secret_async(password)
    rows = [{**a, "password_hash": hashed} for a in adults]
    await _upsert(session, User, rows, insert_only=("password_hash",))
    stale = [
        uid for uid, current in existing.items() if not await verify_secret_async(password, current)
    ]
    for user in (await session.scalars(select(User).where(User.id.in_(stale)))).all():
        # Нова епоха облікових даних: видані токени й push-підписки зі старим паролем
        # перестають діяти.
        user.password_hash = hashed
        await revoke_all_sessions(session, user)
    return generated, True


async def seed(
    session: AsyncSession,
    settings: Settings,
    *,
    today: dt.date | None = None,
    password: str | None = None,
) -> SeedResult:
    if settings.environment == "prod":
        raise SeedRefused("Seed data is not allowed when ENVIRONMENT=prod")
    tz = ZoneInfo(c.SCHOOL["timezone"])
    today = today or dt.datetime.now(tz).date()
    start_year = academic_year_start(today)
    academic_year = f"{start_year.year}/{start_year.year + 1}"

    # ---------- школа, класи, люди ----------
    school_id = sid("school")
    await _upsert(
        session,
        School,
        [
            {
                "id": school_id,
                "name": c.SCHOOL["name"],
                "region_code": c.SCHOOL["region_code"],
                "timezone": c.SCHOOL["timezone"],
            }
        ],
    )
    await _upsert(
        session,
        SchoolClass,
        [
            {
                "id": sid("class", k["key"]),
                "school_id": school_id,
                "name": k["name"],
                "grade": k["grade"],
                "academic_year": academic_year,
                "join_code": k["join_code"],
                "join_code_expires_at": None,
            }
            for k in c.CLASSES
        ],
    )

    def adult(role: str, key: str, data: Mapping[str, str], school: uuid.UUID | None) -> dict:
        return {
            "id": sid("user", key),
            "role": role,
            "display_name": data["name"],
            "last_name": data["last_name"],
            "email": data["email"],
            "school_id": school,
        }

    adults = [adult("admin", "admin", c.ADMIN, school_id)]
    adults += [adult("teacher", k["teacher"]["key"], k["teacher"], school_id) for k in c.CLASSES]
    adults += [
        adult("parent", f"parent{i}", {"name": n, "last_name": ln, "email": e}, None)
        for i, (n, ln, e, _) in enumerate(c.PARENTS, start=1)
    ]
    generated, passwords_set = await _adult_users(session, adults, password)

    students: list[dict[str, Any]] = []
    memberships: list[dict[str, Any]] = []
    for k in c.CLASSES:
        class_id = sid("class", k["key"])
        memberships.append(
            {
                "class_id": class_id,
                "user_id": sid("user", k["teacher"]["key"]),
                "member_role": "teacher",
            }
        )
        for i, (name, last) in enumerate(k["students"]):
            student_id = sid("student", k["key"], i)
            students.append(
                {
                    "id": student_id,
                    "role": "student",
                    "display_name": name,
                    "last_name": last,
                    "name_key": name_key(name, last),
                    "school_id": school_id,
                }
            )
            memberships.append(
                {"class_id": class_id, "user_id": student_id, "member_role": "student"}
            )
    new_students = set(r["id"] for r in students) - set(
        await session.scalars(select(User.id).where(User.id.in_([r["id"] for r in students])))
    )
    if new_students:
        # Один хеш PIN на всіх нових учнів демо (argon2 повільний); наявним PIN не змінюємо.
        pin_hash = await hash_secret_async(c.STUDENT_PIN)
        for row in students:
            row["pin_hash"] = pin_hash
    await _upsert(session, User, students, insert_only=("pin_hash",))
    await _insert_once(session, ClassMembership, memberships, keys=("class_id", "user_id"))
    await _insert_once(
        session,
        ParentChild,
        [
            {"parent_id": sid("user", f"parent{i}"), "child_id": sid("student", cls, idx)}
            for i, (_, _, _, (cls, idx)) in enumerate(c.PARENTS, start=1)
        ],
        keys=("parent_id", "child_id"),
    )

    # ---------- предмети й розклад ----------
    await _upsert(
        session,
        Subject,
        [
            {"id": sid("subject", key), "school_id": school_id, "name": name}
            for key, name in c.SUBJECTS.items()
        ],
    )
    slots: list[dict[str, Any]] = []
    for k in c.CLASSES:
        for weekday, subjects in k["week"].items():
            for n, subject in enumerate(subjects):
                starts, ends = c.BELLS[n]
                slots.append(
                    {
                        "id": sid("slot", k["key"], weekday, n),
                        "class_id": sid("class", k["key"]),
                        "subject_id": sid("subject", subject),
                        "weekday": weekday,
                        "starts_at": _time(starts),
                        "ends_at": _time(ends),
                        "valid_from": start_year,
                        "valid_to": None,
                    }
                )
    await _upsert(session, ScheduleSlot, slots)

    # ---------- уроки ----------
    lessons, modules, cards, tests, questions = [], [], [], [], []
    now = dt.datetime.now(dt.UTC)
    grades = {k["key"]: k["grade"] for k in c.CLASSES}
    teachers = {k["key"]: sid("user", k["teacher"]["key"]) for k in c.CLASSES}
    for lesson in c.LESSONS:
        key = lesson["key"]
        lesson_id = sid("lesson", key)
        lessons.append(
            {
                "id": lesson_id,
                "subject_id": sid("subject", lesson["subject"]),
                "author_id": teachers[lesson["class"]],
                "title": lesson["title"],
                "shelter_part": lesson["shelter_part"],
                "main_part": lesson["main_part"],
                "status": "published",
                "published_at": now,
                "grade": grades[lesson["class"]],
            }
        )
        positions: dict[str, int] = {}
        for m, (part, title, minutes, texts) in enumerate(lesson["modules"]):
            positions[part] = positions.get(part, 0) + 1
            module_id = sid("module", key, m)
            modules.append(
                {
                    "id": module_id,
                    "lesson_id": lesson_id,
                    "part": part,
                    "position": positions[part],
                    "title": title,
                    "duration_min": minutes,
                }
            )
            cards += [
                {
                    "id": sid("card", key, m, j),
                    "module_id": module_id,
                    "position": j + 1,
                    "kind": "text",
                    "body": {"text": text},
                    "media_asset_id": None,
                }
                for j, text in enumerate(texts)
            ]
        test = lesson["test"]
        test_id = sid("test", key)
        tests.append(
            {
                "id": test_id,
                "lesson_id": lesson_id,
                "title": test["title"],
                "window_enabled": test["window_hours"] is not None,
                "window_hours": test["window_hours"],
            }
        )
        for q, (prompt, options, correct) in enumerate(test["questions"]):
            questions.append(
                {
                    "id": sid("question", key, q),
                    "test_id": test_id,
                    "position": q + 1,
                    "kind": "single" if len(correct) == 1 else "multiple",
                    "prompt": prompt,
                    "options": [{"id": OPTION_IDS[i], "text": t} for i, t in enumerate(options)],
                    "answer_key": [OPTION_IDS[i] for i in correct],
                    "points": 1,
                }
            )
    await _upsert(session, Lesson, lessons, insert_only=("published_at",))
    await _upsert(session, Module, modules)
    await _upsert(session, Card, cards)
    await _upsert(session, Test, tests)
    await _upsert(session, Question, questions)

    # ---------- уроки в розкладі: поточний і наступний тиждень ----------
    monday = today - dt.timedelta(days=today.isoweekday() - 1)
    assignments: list[dict[str, Any]] = []
    for k in c.CLASSES:
        by_subject: dict[str, list[uuid.UUID]] = {}
        for lesson in c.LESSONS:
            if lesson["class"] == k["key"]:
                by_subject.setdefault(lesson["subject"], []).append(sid("lesson", lesson["key"]))
        for offset in range(14):
            day = monday + dt.timedelta(days=offset)
            for n, subject in enumerate(k["week"].get(day.isoweekday(), [])):
                options = by_subject.get(subject)
                if not options:
                    continue
                index = subject_occurrence(k["week"], day, n) % len(options)
                assignments.append(
                    {
                        "slot_id": sid("slot", k["key"], day.isoweekday(), n),
                        "date": day,
                        "lesson_id": options[index],
                    }
                )
    await _upsert(session, LessonAssignment, assignments, keys=("slot_id", "date"))

    # ---------- тренувальна тривога й закрита перекличка ----------
    drill_class = next(k for k in c.CLASSES if k["key"] == c.DRILL["class"])
    drill_day = previous_school_day(today)
    started = dt.datetime.combine(drill_day, _time(c.DRILL["starts_at"]), tzinfo=tz)
    ended = dt.datetime.combine(drill_day, _time(c.DRILL["ends_at"]), tzinfo=tz)
    class_id = sid("class", drill_class["key"])
    teacher_id = teachers[drill_class["key"]]
    alert_id, session_id = sid("drill", "alert"), sid("drill", "rollcall")
    await _insert_once(
        session,
        AlertEvent,
        [
            {
                "id": alert_id,
                "region_code": c.SCHOOL["region_code"],
                "school_id": school_id,
                "class_id": class_id,
                "source": "manual",
                "external_id": None,
                "is_drill": True,
                "started_at": started,
                "ended_at": ended,
                "created_by": teacher_id,
            }
        ],
    )
    await _insert_once(
        session,
        RollCallSession,
        [
            {
                "id": session_id,
                "class_id": class_id,
                "alert_event_id": alert_id,
                "opened_by": teacher_id,
                "is_drill": True,
                "opened_at": started,
                "closed_at": ended,
            }
        ],
    )
    events, statuses = [], []
    for idx, status, minute in c.DRILL["statuses"]:
        student_id = sid("student", drill_class["key"], idx)
        event_id = sid("drill", "status", idx)
        occurred = started + dt.timedelta(minutes=minute)
        events.append(
            {
                "client_event_id": event_id,
                "type": "rollcall_status",
                "user_id": student_id,
                "device_id": sid("device", drill_class["key"], idx),
                "occurred_at": occurred,
                "received_at": occurred + dt.timedelta(seconds=2),
                "clock_skew_ms": 0,
                "source": "online",
                "payload": {"session_id": str(session_id), "status": status},
                "status": "accepted",
            }
        )
        statuses.append(
            {
                "session_id": session_id,
                "student_id": student_id,
                "status": status,
                "occurred_at": occurred,
                "received_at": occurred + dt.timedelta(seconds=2),
                "last_event_id": event_id,
            }
        )
    await _insert_once(session, SyncEvent, events, keys=("client_event_id",))
    await _insert_once(session, RollCallStatus, statuses, keys=("session_id", "student_id"))
    await session.commit()

    # ---------- перевірки публікації та пакети ----------
    problems: dict[str, list[dict[str, Any]]] = {}
    for row in lessons:
        lesson_obj = await session.get(Lesson, row["id"])
        assert lesson_obj is not None
        found = await publish_problems(session, lesson_obj, settings)
        if found:
            problems[row["title"]] = found
    packs_built = 0
    for k in c.CLASSES:
        built = await packs_service.rebuild_class(
            session, sid("class", k["key"]), settings, start=today
        )
        packs_built += len(built)

    return SeedResult(
        school_id=school_id,
        join_codes={k["name"]: k["join_code"] for k in c.CLASSES},
        adult_emails=[a["email"] for a in adults],
        generated_password=generated,
        passwords_set=passwords_set,
        lessons=len(lessons),
        packs_built=packs_built,
        problems=problems,
    )
