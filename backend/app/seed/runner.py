"""Демо-дані: `python -m app.cli seed` (B2.7).

Ідемпотентно: id — uuid5 від фіксованого простору імен, рядки вставляються як upsert (оновлення
лише тоді, коли дані справді змінилися), тож повторний запуск того самого дня нічого не змінює.
Розклад і прив'язки уроків рахуються від «сьогодні» (поточний і наступний тиждень), пакети
«Рюкзака» перезбираються на 7 днів. Облікові дані задаються лише при створенні акаунта.

Уроки — `content.LESSONS` плюс доповнення з `lessons_extra.json` (нові модулі, картки з
медіа, пояснення й нові питання тестів). Медіафайли з `app/seed/media/` проходять звичайне
завантаження (`services/media.upload`: перевірка, WebP, дедуплікація) у справжнє сховище;
повтор із тим самим id і вмістом нічого не пише. Файл, якого не стало у сховищі (новий том),
записується знову.
"""

import datetime as dt
import hashlib
import json
import logging
import secrets
import uuid
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import anyio
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_secret_async, verify_secret_async
from app.core.storage import LocalMediaStorage, MediaStorage
from app.models.alerts import AlertEvent
from app.models.lessons import Card, Lesson, MediaAsset, Module, Question, Subject, Test
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
from app.services import media as media_service
from app.services import packs as packs_service
from app.services.auth import name_key, revoke_all_sessions
from app.services.lessons import publish_problems

logger = logging.getLogger(__name__)

# Простір імен демо-даних: однакові ключі → однакові id при кожному запуску.
NAMESPACE = uuid.UUID("5e1d0a7a-2b6f-4c1e-9a43-0d3f5e8c7b21")
OPTION_IDS = "abcdefghij"
SEED_DIR = Path(__file__).resolve().parent
MEDIA_DIR = SEED_DIR / "media"
MEDIA_TYPES = {
    ".mp4": ("video", "video/mp4"),
    ".vtt": ("subtitles", "text/vtt"),
    ".jpg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
}
# Позиції зсуваються за межі допустимих, перш ніж стати остаточними (UNIQUE не відкладений).
POSITION_SHIFT = 2000


@cache
def lessons_extra() -> dict[str, Any]:
    """Доповнення уроків (`lessons_extra.json`): ключ уроку → нові модулі, картки, пояснення,
    питання."""
    data = json.loads((SEED_DIR / "lessons_extra.json").read_text(encoding="utf-8"))
    data.pop("_format", None)
    return data


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


async def _free_positions(session: AsyncSession, model: Any, rows: list[dict[str, Any]]) -> None:
    """Уже засіяні рядки, чия позиція змінюється (новий модуль посередині уроку), спершу
    зсуваються за межі допустимих: UNIQUE (батько, позиція) перевіряється на кожному рядку."""
    wanted = {r["id"]: r["position"] for r in rows}
    current = await session.execute(
        select(model.id, model.position).where(model.id.in_(list(wanted)))
    )
    moved = [i for i, pos in current if pos != wanted[i]]
    if moved:
        await session.execute(
            update(model)
            .where(model.id.in_(moved))
            .values(position=model.position + POSITION_SHIFT)
        )


async def _once(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _seed_media(
    session: AsyncSession,
    storage: MediaStorage,
    settings: Settings,
    teachers: Mapping[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Медіа карток доповнень: файл → id `media_asset`. Власник — вчитель класу уроку; підпис
    автора й ліцензії — з `content.MEDIA`; VTT прив'язуються до відео."""
    owners: dict[str, uuid.UUID] = {}
    subtitles: dict[str, str] = {}
    for lesson in c.LESSONS:
        for card in lessons_extra().get(lesson["key"], {}).get("cards", []):
            for name in (card.get("media"), card.get("subtitles")):
                if name:
                    owners.setdefault(name, teachers[lesson["class"]])
            if card.get("subtitles"):
                subtitles[card["media"]] = card["subtitles"]
    users = {
        u.id: u for u in await session.scalars(select(User).where(User.id.in_(owners.values())))
    }
    ids: dict[str, uuid.UUID] = {}
    for name in sorted(owners):
        kind, mime = MEDIA_TYPES[Path(name).suffix]
        author, license_name, source_url = c.MEDIA.get(name, c.OWN_MEDIA)
        attribution = f"Автор: {author} · {license_name}"
        if source_url is not None:
            attribution += " · Wikimedia Commons"
        data = (MEDIA_DIR / name).read_bytes()
        media, _ = await media_service.upload(
            session,
            storage,
            users[owners[name]],
            media_id=sid("media", name),
            kind=kind,
            content_type=mime,
            content_length=len(data),
            chunks=_once(data),
            settings=settings,
            attribution=attribution,
            source_url=source_url,
        )
        await _restore_file(storage, settings, media, data)
        if (media.attribution, media.source_url) != (attribution, source_url):
            media.attribution, media.source_url = attribution, source_url
        ids[name] = media.id
    for video, vtt in subtitles.items():
        await session.execute(
            update(MediaAsset)
            .where(MediaAsset.id == ids[video], MediaAsset.subtitles_id.is_distinct_from(ids[vtt]))
            .values(subtitles_id=ids[vtt])
        )
    return ids


async def _restore_file(
    storage: MediaStorage, settings: Settings, media: MediaAsset, data: bytes
) -> None:
    """Запис є, а файла у сховищі немає (сід у наявну БД з порожнім томом): записати знову той
    самий вміст (зображення — тим самим перекодуванням), якщо хеш збігається."""
    try:
        path = storage.local_path(media.storage_key)
    except NotImplementedError:
        return
    if await anyio.Path(path).is_file():
        return
    if media.kind == "image" and media.mime_type == "image/webp":
        webp = await anyio.to_thread.run_sync(
            media_service._to_webp,
            data,
            settings.media_image_max_side,
            settings.media_image_webp_quality,
            settings.media_image_max_pixels,
            settings.media_image_max_pixels_full_decode,
        )
        data = webp or data
    if hashlib.sha256(data).hexdigest() != media.sha256:
        logger.warning("Seed media %s is missing in storage and differs, skipped", media.id)
        return
    await storage.save(media.storage_key, _once(data))


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
    storage: MediaStorage | None = None,
) -> SeedResult:
    if settings.environment == "prod":
        raise SeedRefused("Seed data is not allowed when ENVIRONMENT=prod")
    storage = storage or LocalMediaStorage(settings.media_root, settings.media_url_prefix)
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
    media_ids = await _seed_media(session, storage, settings, teachers)
    for lesson in c.LESSONS:
        key = lesson["key"]
        lesson_id = sid("lesson", key)
        extra = lessons_extra().get(key, {})
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
        # Модулі по порядку: (ключ для id, частина, назва, хвилини, картки). Ключ наявних —
        # індекс у LESSONS (id не змінюються), нових модулів із доповнень — назва.
        ordered: list[tuple[object, str, str, int, list[dict[str, Any]]]] = [
            (m, part, title, minutes, [{"kind": "text", "body": {"text": t}} for t in texts])
            for m, (part, title, minutes, texts) in enumerate(lesson["modules"])
        ]
        for new in extra.get("new_modules", []):
            after = next(i for i, m in enumerate(ordered) if m[2] == new["after_module"])
            ordered.insert(
                after + 1,
                (f"extra:{new['title']}", new["part"], new["title"], new["minutes"], []),
            )
        by_title = {m[2]: m[4] for m in ordered}
        for card in extra.get("cards", []):
            if card["kind"] == "text":
                by_title[card["module"]].append({"kind": "text", "body": {"text": card["text"]}})
            else:
                by_title[card["module"]].append(
                    {
                        "kind": card["kind"],
                        "body": {"caption": card["caption"]},
                        "media_asset_id": media_ids[card["media"]],
                    }
                )
        positions: dict[str, int] = {}
        for ident, part, title, minutes, module_cards in ordered:
            positions[part] = positions.get(part, 0) + 1
            module_id = sid("module", key, ident)
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
                    "id": sid("card", key, ident, j),
                    "module_id": module_id,
                    "position": j + 1,
                    "kind": card["kind"],
                    "body": card["body"],
                    "media_asset_id": card.get("media_asset_id"),
                }
                for j, card in enumerate(module_cards)
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
        explanations: dict[int, str] = {}
        for e in extra.get("explanations", []):
            # Звірка: пояснення належить тому самому питанню, що й у LESSONS.
            if test["questions"][e["index"]][0] != e["question"]:
                raise ValueError(f"Explanation does not match question {key}/{e['index']}")
            explanations[e["index"]] = e["explanation"]
        for q, (prompt, options, correct) in enumerate(test["questions"]):
            questions.append(
                {
                    "id": sid("question", key, q),
                    "test_id": test_id,
                    "position": q + 1,
                    "kind": "single" if len(correct) == 1 else "multiple",
                    "prompt": prompt,
                    "options": [{"id": OPTION_IDS[i], "text": t} for i, t in enumerate(options)],
                    "right_options": None,
                    "answer_key": [OPTION_IDS[i] for i in correct],
                    "points": 1,
                    "explanation": explanations.get(q),
                }
            )
        for n, extra_q in enumerate(extra.get("new_questions", []), start=len(test["questions"])):
            questions.append(
                {
                    "id": sid("question", key, n),
                    "test_id": test_id,
                    "position": n + 1,
                    "kind": extra_q["kind"],
                    "prompt": extra_q["prompt"],
                    "options": extra_q["options"],
                    "right_options": extra_q.get("right_options"),
                    "answer_key": extra_q["answer_key"],
                    "points": 1,
                    "explanation": extra_q.get("explanation"),
                }
            )
    await _upsert(session, Lesson, lessons, insert_only=("published_at",))
    await _free_positions(session, Module, modules)
    await _upsert(session, Module, modules)
    await _free_positions(session, Card, cards)
    await _upsert(session, Card, cards)
    await _upsert(session, Test, tests)
    await _free_positions(session, Question, questions)
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
