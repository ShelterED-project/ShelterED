import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models.school import SchoolClass, User
from app.services import auth as auth_service

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


AccessibleClass = Annotated[SchoolClass, Depends(get_accessible_class)]
StaffClass = Annotated[SchoolClass, Depends(get_staff_class)]
AccessibleStudent = Annotated[User, Depends(get_accessible_student)]
