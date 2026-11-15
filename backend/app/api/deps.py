import uuid
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter, RedisRateLimiter
from app.core.security import decode_access_token
from app.core.storage import LocalMediaStorage, MediaStorage
from app.models.lessons import Card, Lesson, Module, Question, Test
from app.models.school import SchoolClass, User
from app.services import auth as auth_service
from app.services import lessons as lessons_service

bearer_scheme = HTTPBearer(auto_error=False, description="Access-токен (JWT)")

Session = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Session,
    settings: SettingsDep,
) -> User:
    if credentials is None:
        raise AppError("UNAUTHORIZED", "Not authenticated", status_code=401)
    claims = decode_access_token(credentials.credentials, settings)
    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active or user.token_version != claims["ver"]:
        raise AppError("UNAUTHORIZED", "Invalid or expired token", status_code=401)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[[User], Awaitable[User]]:
    """Залежність: пропускає лише вказані ролі, інакше 403."""

    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "Insufficient permissions", status_code=403)
        return user

    return dependency


Admin = Annotated[User, Depends(require_roles("admin"))]
Parent = Annotated[User, Depends(require_roles("parent"))]
Staff = Annotated[User, Depends(require_roles("teacher", "admin"))]
Teacher = Annotated[User, Depends(require_roles("teacher"))]


async def get_accessible_class(
    class_id: uuid.UUID, user: CurrentUser, session: Session
) -> SchoolClass:
    """Клас, до якого в користувача є доступ (див. can_access_class), інакше 403/404."""
    klass = await auth_service.get_class(session, class_id)
    if klass is None:
        raise AppError("NOT_FOUND", "Class not found", status_code=404)
    if not await auth_service.can_access_class(session, user, klass):
        raise AppError("FORBIDDEN", "No access to this class", status_code=403)
    return klass


async def get_staff_class(class_id: uuid.UUID, user: Staff, session: Session) -> SchoolClass:
    """Те саме, але лише для вчителя класу або адміна його школи."""
    return await get_accessible_class(class_id, user, session)


async def get_accessible_student(
    student_id: uuid.UUID, user: CurrentUser, session: Session
) -> User:
    """Учень, дані якого користувач має право бачити (див. can_access_student)."""
    student = await session.get(User, student_id)
    if student is None or student.role != "student":
        raise AppError("NOT_FOUND", "Student not found", status_code=404)
    if not await auth_service.can_access_student(session, user, student):
        raise AppError("FORBIDDEN", "No access to this student", status_code=403)
    return student


async def get_cabinet_student(
    student_id: uuid.UUID,
    user: Annotated[User, Depends(require_roles("student", "parent", "teacher"))],
    session: Session,
) -> User:
    """Кабінет учня (прогрес, мапа знань): учень — себе, батьки — свою дитину, вчитель — учнів
    своїх класів; адміністрація — ні (навчальні дані учня їй не потрібні)."""
    return await get_accessible_student(student_id, user, session)


AccessibleClass = Annotated[SchoolClass, Depends(get_accessible_class)]
StaffClass = Annotated[SchoolClass, Depends(get_staff_class)]
AccessibleStudent = Annotated[User, Depends(get_accessible_student)]
CabinetStudent = Annotated[User, Depends(get_cabinet_student)]


async def get_admin_class(class_id: uuid.UUID, user: Admin, session: Session) -> SchoolClass:
    """Клас школи адміна (керування класом і розкладом), інакше 403/404."""
    return await get_accessible_class(class_id, user, session)


async def get_teacher_class(class_id: uuid.UUID, user: Teacher, session: Session) -> SchoolClass:
    """Клас, у якому користувач — вчитель (прив'язка уроків до розкладу)."""
    return await get_accessible_class(class_id, user, session)


AdminClass = Annotated[SchoolClass, Depends(get_admin_class)]
TeacherClass = Annotated[SchoolClass, Depends(get_teacher_class)]


# ---------- уроки: читає автор і персонал його школи, змінює лише автор ----------


async def get_readable_lesson(lesson_id: uuid.UUID, user: Staff, session: Session) -> Lesson:
    return await lessons_service.get_readable_lesson(session, user, lesson_id)


async def get_editable_lesson(lesson_id: uuid.UUID, user: Teacher, session: Session) -> Lesson:
    """Чернетка автора (опублікований урок — 409 LESSON_PUBLISHED)."""
    return await lessons_service.get_editable_lesson(session, user, lesson_id)


async def get_own_lesson(lesson_id: uuid.UUID, user: Teacher, session: Session) -> Lesson:
    """Урок автора в будь-якому статусі (публікація, зняття з публікації)."""
    return await lessons_service.get_editable_lesson(session, user, lesson_id, require_draft=False)


async def get_editable_module(module_id: uuid.UUID, user: Teacher, session: Session) -> Module:
    return await lessons_service.get_editable_module(session, user, module_id)


async def get_editable_card(card_id: uuid.UUID, user: Teacher, session: Session) -> Card:
    return await lessons_service.get_editable_card(session, user, card_id)


async def get_editable_test(test_id: uuid.UUID, user: Teacher, session: Session) -> Test:
    return await lessons_service.get_editable_test(session, user, test_id)


async def get_editable_question(
    question_id: uuid.UUID, user: Teacher, session: Session
) -> Question:
    return await lessons_service.get_editable_question(session, user, question_id)


ReadableLesson = Annotated[Lesson, Depends(get_readable_lesson)]
EditableLesson = Annotated[Lesson, Depends(get_editable_lesson)]
OwnLesson = Annotated[Lesson, Depends(get_own_lesson)]
EditableModule = Annotated[Module, Depends(get_editable_module)]
EditableCard = Annotated[Card, Depends(get_editable_card)]
EditableTest = Annotated[Test, Depends(get_editable_test)]
EditableQuestion = Annotated[Question, Depends(get_editable_question)]


def get_storage(settings: SettingsDep) -> MediaStorage:
    """Сховище медіа; у тестах підміняється через dependency_overrides."""
    return LocalMediaStorage(settings.media_root, settings.media_url_prefix)


Storage = Annotated[MediaStorage, Depends(get_storage)]


@lru_cache
def _redis_rate_limiter(url: str) -> RedisRateLimiter:
    return RedisRateLimiter(url)


def get_rate_limiter(settings: SettingsDep) -> RateLimiter:
    """Rate limiter входу; у тестах підміняється через dependency_overrides."""
    return _redis_rate_limiter(settings.rate_limit_redis_url)


Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]
