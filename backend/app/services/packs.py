"""Пакети знань «Рюкзак» (B6): збірка, версії, маніфест, вміст.

Пакет = клас + дата: розклад дня, опубліковані уроки дня (модулі, картки, тести без ключа
відповідей), закешовані пояснення ШІ (поки порожні: сховища пояснень немає, B13.3).
Медіа в пакет не вкладаються: їх URL і розміри — у маніфесті, Service Worker кешує окремо.

Збірка детермінована: хеш — sha256 канонічного JSON (сортовані ключі, без пробілів) вмісту без
id, версії й часу збірки. Той самий вміст → той самий хеш → нова версія не створюється, тож
повторна чи паралельна перезбірка нічого не дублює. Версія незмінна; стара лишається доступною.
"""

import datetime as dt
import gzip
import hashlib
import json
import logging
import uuid
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.config import Settings
from app.core.errors import AppError
from app.core.storage import MediaStorage
from app.models.lessons import Card, Lesson, MediaAsset, Module, Question, Test
from app.models.packs import KnowledgePack, KnowledgePackLesson, KnowledgePackMedia
from app.models.school import LessonAssignment, ScheduleSlot, SchoolClass
from app.schemas.lessons import CardOut, ModuleOut, Option
from app.schemas.packs import (
    MediaManifestItem,
    PackLesson,
    PackManifestItem,
    PackManifestOut,
    PackQuestion,
    PackTest,
)
from app.schemas.school import ScheduleItem
from app.services import lessons as lessons_service
from app.services import school as school_service
from app.services.schedule import ResolvedItem, local_date
from app.workers.push import enqueue_push

logger = logging.getLogger(__name__)

# Текст і тести — на 7 днів, медіа — на «сьогодні + завтра».
HORIZON_DAYS = 7
MEDIA_HORIZON_DAYS = 2
# Скільки разів перезбирати пакет, якщо паралельна збірка зайняла ту саму версію.
BUILD_ATTEMPTS = 3

# Розклад дня, уже розв'язаний для класу: (пояс школи, уроки дня).
DaySchedule = tuple[ZoneInfo, list[ResolvedItem]]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def content_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body)).hexdigest()


# ---------- вміст пакета ----------


async def _lesson_content(
    session: AsyncSession, lesson: Lesson
) -> tuple[PackLesson, set[uuid.UUID]]:
    """Урок у пакеті + id його медіа (з субтитрами)."""
    modules = list(await session.scalars(select(Module).where(Module.lesson_id == lesson.id)))
    modules.sort(key=lambda m: (0 if m.part == "shelter" else 1, m.position))
    cards = list(
        await session.scalars(
            select(Card)
            .where(Card.module_id.in_([m.id for m in modules]))
            .order_by(Card.module_id, Card.position)
        )
    )
    by_module: dict[uuid.UUID, list[CardOut]] = {}
    media: set[uuid.UUID] = set()
    for c in cards:
        by_module.setdefault(c.module_id, []).append(CardOut.model_validate(c))
        if c.media_asset_id is not None:
            media.add(c.media_asset_id)
    if media:
        subtitles = await session.scalars(
            select(MediaAsset.subtitles_id).where(
                MediaAsset.id.in_(media), MediaAsset.subtitles_id.is_not(None)
            )
        )
        media.update(s for s in subtitles if s is not None)

    tests = list(
        await session.scalars(
            select(Test).where(Test.lesson_id == lesson.id).order_by(Test.created_at, Test.id)
        )
    )
    questions = list(
        await session.scalars(
            select(Question)
            .where(Question.test_id.in_([t.id for t in tests]))
            .order_by(Question.test_id, Question.position)
        )
    )
    pack_tests = [
        PackTest(
            id=t.id,
            title=t.title,
            window_enabled=t.window_enabled,
            window_hours=t.window_hours,
            # Ключа відповідей у пакеті немає (B11.4 не вирішено): перевіряє сервер.
            questions=[
                PackQuestion(
                    id=q.id,
                    position=q.position,
                    kind=q.kind,  # type: ignore[arg-type]
                    prompt=q.prompt,
                    options=[Option.model_validate(o) for o in q.options],
                    points=q.points,
                )
                for q in questions
                if q.test_id == t.id
            ],
        )
        for t in tests
    ]
    return (
        PackLesson(
            id=lesson.id,
            version=lesson.version,
            subject_id=lesson.subject_id,
            title=lesson.title,
            shelter_part=lesson.shelter_part,
            main_part=lesson.main_part,
            modules=[
                ModuleOut(
                    id=m.id,
                    lesson_id=m.lesson_id,
                    part=m.part,
                    position=m.position,
                    title=m.title,
                    duration_min=m.duration_min,
                    cards=by_module.get(m.id, []),
                )
                for m in modules
            ],
            tests=pack_tests,
        ),
        media,
    )


async def build_content(
    session: AsyncSession, klass: SchoolClass, day: dt.date, resolved: DaySchedule | None = None
) -> tuple[dict[str, Any], dict[uuid.UUID, int], set[uuid.UUID]]:
    """(вміст без id/версії/часу збірки, {lesson_id: version}, id медіа). Лише опубліковані
    уроки: якщо призначений урок знято з публікації, у розкладі пакета `lesson_id = null`.
    `resolved` — уже розв'язаний розклад дня (інакше читається з БД)."""
    if resolved is None:
        tz, days = await school_service.class_schedule(session, klass, day, 1)
        resolved = (tz, days[0][1])
    tz, items = resolved
    wanted = list(dict.fromkeys(i.lesson_id for i in items if i.lesson_id is not None))
    lessons = {
        lesson.id: lesson
        for lesson in await session.scalars(
            select(Lesson).where(Lesson.id.in_(wanted), Lesson.status == "published")
        )
    }
    schedule = []
    for i in items:
        item = ScheduleItem.model_validate(i, from_attributes=True)
        if item.lesson_id not in lessons:
            item.lesson_id = None
        schedule.append(item.model_dump(mode="json"))

    pack_lessons: list[dict[str, Any]] = []
    versions: dict[uuid.UUID, int] = {}
    media: set[uuid.UUID] = set()
    for lesson_id in wanted:
        lesson = lessons.get(lesson_id)
        if lesson is None:
            continue
        content, lesson_media = await _lesson_content(session, lesson)
        pack_lessons.append(content.model_dump(mode="json"))
        versions[lesson.id] = lesson.version
        media |= lesson_media
    body = {
        "class_id": str(klass.id),
        "pack_date": day.isoformat(),
        "timezone": tz.key,
        "schedule": schedule,
        "lessons": pack_lessons,
        # Закешовані пояснення ШІ (B13.3): сховища ще немає.
        "explanations": [],
        # Медіа й субтитри: заміна субтитрів відео змінює хеш, а отже й версію пакета.
        "media": sorted(str(m) for m in media),
    }
    return body, versions, media


# Метадані пакета без вмісту: стиснутий JSON читає лише `GET /packs/{id}`.
_NO_CONTENT = defer(KnowledgePack.content_gzip, raiseload=True)


async def latest_pack(
    session: AsyncSession, class_id: uuid.UUID, day: dt.date
) -> KnowledgePack | None:
    """Найновіша версія пакета дня (без `content_gzip`)."""
    return await session.scalar(
        select(KnowledgePack)
        .options(_NO_CONTENT)
        .where(KnowledgePack.class_id == class_id, KnowledgePack.pack_date == day)
        .order_by(KnowledgePack.version.desc())
        .limit(1)
    )


async def _latest_packs(
    session: AsyncSession, class_id: uuid.UUID, start: dt.date, end: dt.date
) -> list[KnowledgePack]:
    """Найновіша версія кожного дня `start`..`end` (без `content_gzip`), за датою."""
    rows = await session.scalars(
        select(KnowledgePack)
        .options(_NO_CONTENT)
        .where(
            KnowledgePack.class_id == class_id,
            KnowledgePack.pack_date >= start,
            KnowledgePack.pack_date <= end,
        )
        .order_by(KnowledgePack.pack_date, KnowledgePack.version.desc())
        .ext(distinct_on(KnowledgePack.pack_date))
    )
    return list(rows)


async def build_pack(
    session: AsyncSession,
    klass: SchoolClass,
    day: dt.date,
    settings: Settings,
    now: dt.datetime | None = None,
    resolved: DaySchedule | None = None,
) -> tuple[KnowledgePack | None, bool]:
    """Збирає пакет класу на дату. (пакет, True) — нова версія; (актуальний, False) — вміст
    не змінився; (None, False) — дня без уроків у розкладі ще не було в пакетах.
    Якщо паралельна збірка зайняла ту саму версію, дані перечитуються й пакет збирається
    знову (до BUILD_ATTEMPTS разів): виграють найсвіжіші дані, а не те, що встигло першим.
    Commit робить викликач."""
    now = now or _now()
    for _ in range(BUILD_ATTEMPTS):
        pack, created, conflict = await _try_build(session, klass, day, settings, now, resolved)
        if not conflict:
            return pack, created
        resolved = None  # розклад теж міг змінитися — перечитуємо все
    logger.warning("Pack build gave up after version conflicts: class=%s date=%s", klass.id, day)
    return await latest_pack(session, klass.id, day), False


async def _try_build(
    session: AsyncSession,
    klass: SchoolClass,
    day: dt.date,
    settings: Settings,
    now: dt.datetime,
    resolved: DaySchedule | None,
) -> tuple[KnowledgePack | None, bool, bool]:
    """Одна спроба збірки: (пакет, створено, конфлікт версії)."""
    body, versions, media = await build_content(session, klass, day, resolved)
    latest = await latest_pack(session, klass.id, day)
    if latest is None and not body["schedule"]:
        return None, False, False
    digest = content_hash(body)
    if latest is not None and latest.content_hash == digest:
        return latest, False, False

    pack_id = uuid.uuid4()
    version = (latest.version if latest else 0) + 1
    full = {
        **body,
        "id": str(pack_id),
        "version": version,
        "content_hash": digest,
        "built_at": now.isoformat().replace("+00:00", "Z"),
    }
    raw = canonical_json(full)
    inserted = await session.scalar(
        pg_insert(KnowledgePack)
        .values(
            id=pack_id,
            class_id=klass.id,
            pack_date=day,
            version=version,
            content_hash=digest,
            size_bytes=len(raw),
            built_at=now,
            content_gzip=gzip.compress(raw, mtime=0),
        )
        .on_conflict_do_nothing(constraint="uq_knowledge_pack_version")
        .returning(KnowledgePack.id)
    )
    if inserted is None:
        # Паралельна збірка вже створила цю версію (можливо, зі старіших даних).
        return None, False, True
    if versions:
        await session.execute(
            pg_insert(KnowledgePackLesson).values(
                [
                    {"pack_id": pack_id, "lesson_id": lid, "lesson_version": v}
                    for lid, v in versions.items()
                ]
            )
        )
    if media:
        await session.execute(
            pg_insert(KnowledgePackMedia).values(
                [{"pack_id": pack_id, "media_asset_id": m} for m in sorted(media)]
            )
        )
    media_bytes = await lessons_service.media_size(session, media)
    logger.info(
        "Pack built: class=%s date=%s version=%d json_bytes=%d media_bytes=%d",
        klass.id,
        day,
        version,
        len(raw),
        media_bytes,
    )
    if len(raw) + media_bytes > settings.pack_max_day_bytes:
        logger.warning(
            "Pack exceeds day limit: class=%s date=%s bytes=%d limit=%d",
            klass.id,
            day,
            len(raw) + media_bytes,
            settings.pack_max_day_bytes,
        )
    pack = await session.get(KnowledgePack, pack_id)
    return pack, True, False


async def _week_size(
    session: AsyncSession, class_id: uuid.UUID, start: dt.date, end: dt.date
) -> int:
    packs = await _latest_packs(session, class_id, start, end)
    if not packs:
        return 0
    media = set(
        await session.scalars(
            select(KnowledgePackMedia.media_asset_id).where(
                KnowledgePackMedia.pack_id.in_([p.id for p in packs])
            )
        )
    )
    return sum(p.size_bytes for p in packs) + await lessons_service.media_size(session, media)


async def rebuild_class(
    session: AsyncSession,
    class_id: uuid.UUID,
    settings: Settings,
    start: dt.date | None = None,
    now: dt.datetime | None = None,
) -> list[KnowledgePack]:
    """Перезбирає пакети класу на 7 днів від `start` (за замовчуванням сьогодні в поясі
    школи). Якщо з'явилась хоч одна нова версія — один push «рюкзак оновився» класу.
    Ідемпотентно: без змін вмісту нічого не пише й push не ставить."""
    klass = await session.get(SchoolClass, class_id)
    if klass is None:
        return []
    now = now or _now()
    if start is None:
        start = local_date(now, await school_service.school_tz(session, klass.school_id))
    built: list[KnowledgePack] = []
    # Розклад тижня — одним читанням, а не на кожен день.
    tz, days = await school_service.class_schedule(session, klass, start, HORIZON_DAYS)
    for day, items in days:
        pack, created = await build_pack(session, klass, day, settings, now, (tz, items))
        if created and pack is not None:
            built.append(pack)
    await session.commit()
    if built:
        end = start + dt.timedelta(days=HORIZON_DAYS - 1)
        week = await _week_size(session, klass.id, start, end)
        if week > settings.pack_max_week_bytes:
            logger.warning(
                "Class packs exceed week limit: class=%s from=%s bytes=%d limit=%d",
                klass.id,
                start,
                week,
                settings.pack_max_week_bytes,
            )
        first = min(built, key=lambda p: p.pack_date)
        enqueue_push("pack_updated", class_id=klass.id, pack_id=first.id, pack_date=first.pack_date)
    return built


async def classes_with_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, start: dt.date, end: dt.date
) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(ScheduleSlot.class_id)
        .join(LessonAssignment, LessonAssignment.slot_id == ScheduleSlot.id)
        .where(
            LessonAssignment.lesson_id == lesson_id,
            LessonAssignment.date >= start,
            LessonAssignment.date <= end,
        )
        .distinct()
        .order_by(ScheduleSlot.class_id)
    )
    return list(rows)


async def rebuild_for_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, settings: Settings
) -> list[KnowledgePack]:
    """Публікація чи зняття уроку з публікації: класи, де урок стоїть у найближчі 7 днів.
    Вікно трохи ширше (вчора..+7), щоб не загубити класи в інших часових поясах."""
    today = _now().date()
    classes = await classes_with_lesson(
        session, lesson_id, today - dt.timedelta(days=1), today + dt.timedelta(days=HORIZON_DAYS)
    )
    built: list[KnowledgePack] = []
    for class_id in classes:
        built += await rebuild_class(session, class_id, settings)
    return built


async def refresh_all(session: AsyncSession, settings: Settings) -> int:
    """Періодична перезбірка всіх класів (новий день, зміни розкладу). Ідемпотентна."""
    class_ids = list(await session.scalars(select(SchoolClass.id).order_by(SchoolClass.id)))
    built = 0
    for class_id in class_ids:
        built += len(await rebuild_class(session, class_id, settings))
    return built


# ---------- маніфест і завантаження ----------


def _bad_range(message: str) -> AppError:
    return AppError("VALIDATION_ERROR", message, status_code=422)


async def manifest(
    session: AsyncSession,
    klass: SchoolClass,
    date_from: dt.date | None,
    date_to: dt.date | None,
    storage: MediaStorage,
) -> PackManifestOut:
    tz = await school_service.school_tz(session, klass.school_id)
    today = local_date(_now(), tz)
    start = date_from or today
    end = date_to or start + dt.timedelta(days=HORIZON_DAYS - 1)
    if end < start:
        raise _bad_range("`to` must not be earlier than `from`")
    if (end - start).days >= HORIZON_DAYS:
        raise _bad_range(f"Range must not exceed {HORIZON_DAYS} days")

    packs = await _latest_packs(session, klass.id, start, end)

    media_from = max(start, today)
    media_to = min(end, today + dt.timedelta(days=MEDIA_HORIZON_DAYS - 1))
    media_packs = {p.id: p.pack_date for p in packs if media_from <= p.pack_date <= media_to}
    media: list[MediaManifestItem] = []
    if media_packs:
        needed_on: dict[uuid.UUID, dt.date] = {}
        assets: dict[uuid.UUID, MediaAsset] = {}
        for pack_id, asset in await session.execute(
            select(KnowledgePackMedia.pack_id, MediaAsset)
            .join(MediaAsset, MediaAsset.id == KnowledgePackMedia.media_asset_id)
            .where(KnowledgePackMedia.pack_id.in_(media_packs))
        ):
            day = media_packs[pack_id]
            assets[asset.id] = asset
            needed_on[asset.id] = min(day, needed_on.get(asset.id, day))
        media = [
            MediaManifestItem(
                id=a.id,
                kind=a.kind,  # type: ignore[arg-type]
                url=storage.url(a.storage_key),
                size_bytes=a.size_bytes,
                sha256=a.sha256,
                subtitles_id=a.subtitles_id,
                needed_on=needed_on[a.id],
            )
            for a in sorted(assets.values(), key=lambda a: (needed_on[a.id], str(a.id)))
        ]
    return PackManifestOut(
        class_id=klass.id,
        date_from=start,
        date_to=end,
        packs=[PackManifestItem.model_validate(p) for p in packs],
        media=media,
    )


async def get_pack(session: AsyncSession, pack_id: uuid.UUID) -> KnowledgePack:
    pack = await session.get(KnowledgePack, pack_id)
    if pack is None:
        raise AppError("NOT_FOUND", "Pack not found", status_code=404)
    return pack
