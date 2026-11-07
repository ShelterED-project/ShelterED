import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal
from urllib.parse import parse_qsl

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import ValidationError

from app.api.deps import (
    AccessibleStudent,
    Admin,
    CurrentUser,
    Limiter,
    Parent,
    Session,
    SettingsDep,
    Staff,
    StaffClass,
)
from app.core.errors import AppError
from app.core.rate_limit import RateLimiter, Rule, rate_limited, rule
from app.core.security import normalize_link_code
from app.schemas.auth import (
    AdminCreateUserRequest,
    AuthorizeRequest,
    AuthorizeResponse,
    LogoutRequest,
    ParentLinkCodeResponse,
    ParentLinkRequest,
    ParentLinkResponse,
    StudentJoinRequest,
    TokenRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.errors import ErrorResponse
from app.services import auth as service
from app.services import school as school_service

router = APIRouter(tags=["auth"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}
R403 = {403: {"model": ErrorResponse, "description": "Недостатньо прав"}}
R404 = {404: {"model": ErrorResponse, "description": "Не знайдено"}}
R429 = {
    429: {
        "model": ErrorResponse,
        "description": "RATE_LIMITED: забагато невдалих спроб; повторити після `Retry-After` с",
        "headers": {"Retry-After": {"schema": {"type": "integer"}}},
    }
}

# Невдалі спроби входу, які рахує rate limiter (успішний вхід не рахується).
_FAILED_LOGIN = {"INVALID_CREDENTIALS", "INVALID_JOIN_CODE"}


def _client_ip(request: Request) -> str:
    # За Nginx `request.client` — це адреса клієнта з X-Forwarded-For лише тоді, коли uvicorn
    # довіряє проксі: `--proxy-headers` + FORWARDED_ALLOW_IPS з IP/підмережею Nginx (Dockerfile).
    # Інакше тут IP Nginx — один спільний лічильник «на IP» і «IP + акаунт» для всіх клієнтів.
    return request.client.host if request.client else "unknown"


async def _limited[T](
    limiter: RateLimiter, rules: list[Rule], call: Callable[[], Awaitable[T]]
) -> T:
    """Вхід із лімітом невдалих спроб: вичерпаний ключ — 429 з Retry-After, без виклику."""
    retry_after = await limiter.retry_after(rules)
    if retry_after is not None:
        raise rate_limited(retry_after, "Too many failed login attempts, try again later")
    try:
        return await call()
    except AppError as exc:
        if exc.code in _FAILED_LOGIN:
            await limiter.hit(rules)
        raise


@router.post(
    "/auth/authorize",
    response_model=AuthorizeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Невідомий client_id"},
        401: {"model": ErrorResponse, "description": "INVALID_CREDENTIALS"},
        **R429,
    },
)
async def authorize(
    body: AuthorizeRequest,
    request: Request,
    session: Session,
    settings: SettingsDep,
    limiter: Limiter,
) -> AuthorizeResponse:
    """OAuth 2.0 Authorization Code + PKCE (S256) для вчителів, батьків, адміністрації.

    Форму входу малює PWA; відповідь — одноразовий `code` (60 с) для `POST /auth/token`.
    Невдалі спроби обмежені на пару IP + email, на IP і високим загальним лімітом на email з
    усіх IP (`RATE_LIMIT_LOGIN_*` за `RATE_LIMIT_WINDOW_S`); понад ліміт — 429 з `Retry-After`.
    Акаунт не блокується: перебір з одного IP не заважає власнику входити з іншого.
    """
    window = settings.rate_limit_window_s
    ip = _client_ip(request)
    rules = [
        rule(
            "login:acct",
            f"{ip}\n{body.email.casefold()}",
            settings.rate_limit_login_account,
            window,
        ),
        rule("login:ip", ip, settings.rate_limit_login_ip, window),
        rule(
            "login:acct_all",
            body.email.casefold(),
            settings.rate_limit_login_account_all_ips,
            window,
        ),
    ]
    code = await _limited(
        limiter,
        rules,
        lambda: service.authorize(
            session,
            email=body.email,
            password=body.password,
            code_challenge=body.code_challenge,
            client_id=body.client_id,
            redirect_uri=body.redirect_uri,
            settings=settings,
        ),
    )
    return AuthorizeResponse(code=code)


async def _read_token_request(request: Request) -> TokenRequest:
    raw = await request.body()
    try:
        if "application/x-www-form-urlencoded" in request.headers.get("content-type", ""):
            data = dict(parse_qsl(raw.decode(), keep_blank_values=False))
        else:
            data = json.loads(raw or b"{}")
        return TokenRequest.model_validate(data)
    except ValidationError as exc:
        # Без "input": у тілі можуть бути токени.
        details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        raise AppError(
            "INVALID_REQUEST", "Invalid token request", status_code=400, details=details
        ) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("INVALID_REQUEST", "Invalid token request", status_code=400) from exc


@router.post(
    "/auth/token",
    response_model=TokenResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": TokenRequest.model_json_schema()},
                "application/x-www-form-urlencoded": {"schema": TokenRequest.model_json_schema()},
            },
        }
    },
    responses={400: {"model": ErrorResponse, "description": "INVALID_GRANT / INVALID_REQUEST"}},
)
async def token(request: Request, session: Session, settings: SettingsDep) -> TokenResponse:
    """Обмін `code` + `code_verifier` на токени або ротація `refresh_token` (RFC 6749).

    Тіло: JSON або `application/x-www-form-urlencoded`. Refresh-токен ротується; повтор уже
    ротованого токена протягом `REFRESH_REUSE_GRACE_SECONDS` (300 с) вважається втраченою
    відповіддю або другою вкладкою, якщо виданий з нього токен ще не використано: видається
    нова пара в тій самій родині. Інакше (пізній повтор, використаний наступник) відкликаються
    всі токени цього входу. Відкликані токени (вихід, скидання PIN) завжди дають `INVALID_GRANT`.
    """
    body = await _read_token_request(request)
    if body.grant_type == "authorization_code":
        if not (body.code and body.code_verifier and body.client_id):
            raise AppError("INVALID_REQUEST", "code, code_verifier and client_id are required", 400)
        return await service.exchange_code(
            session,
            code=body.code,
            code_verifier=body.code_verifier,
            client_id=body.client_id,
            redirect_uri=body.redirect_uri,
            settings=settings,
        )
    if not body.refresh_token:
        raise AppError("INVALID_REQUEST", "refresh_token is required", 400)
    return await service.refresh_tokens(session, body.refresh_token, settings)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, session: Session) -> Response:
    """Відкликає refresh-токен і всю його родину. Ідемпотентний."""
    await service.logout(session, body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=UserOut, responses=R401)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post(
    "/auth/student/join",
    response_model=TokenResponse,
    responses={
        400: {"model": ErrorResponse, "description": "INVALID_JOIN_CODE"},
        401: {"model": ErrorResponse, "description": "INVALID_CREDENTIALS (хибний PIN)"},
        **R429,
    },
)
async def student_join(
    body: StudentJoinRequest,
    request: Request,
    session: Session,
    settings: SettingsDep,
    limiter: Limiter,
) -> TokenResponse:
    """Вхід учня: код класу + імʼя + прізвище + PIN (4–6 цифр).

    Якщо учня з таким імʼям у класі ще немає — його створюють, інакше перевіряють PIN.
    Код класу нормалізується (лише A-Z і 0-9; кириличні двійники латиниці замінюються).
    Прострочений код пускає лише наявних учнів із вірним PIN; для невідомого імені й хибного PIN
    відповідь однакова: 401 `INVALID_CREDENTIALS`.

    Захист від перебору PIN: невдалі спроби обмежені на пару IP + (код класу + ім'я), на IP і
    високим загальним лімітом на (код класу + ім'я) з усіх IP (`RATE_LIMIT_JOIN_*` за
    `RATE_LIMIT_WINDOW_S`) і добовим лімітом на (код класу + ім'я) з усіх IP
    (`RATE_LIMIT_JOIN_ACCOUNT_DAILY`); понад ліміт — 429 з `Retry-After`.
    Блокування акаунта немає: однокласник, що вводить чужий PIN, блокує лише себе (свій IP),
    а справжній учень входить з іншого пристрою/IP; ліміт знімається сам після вікна.
    """
    window = settings.rate_limit_window_s
    ip = _client_ip(request)
    account = f"{normalize_link_code(body.join_code)}\n"
    account += service.name_key(body.display_name, body.last_name)
    rules = [
        rule("join:acct", f"{ip}\n{account}", settings.rate_limit_join_account, window),
        rule("join:ip", ip, settings.rate_limit_join_ip, window),
        rule("join:acct_all", account, settings.rate_limit_join_account_all_ips, window),
        rule(
            "join:acct_day",
            account,
            settings.rate_limit_join_account_daily,
            settings.rate_limit_daily_window_s,
        ),
    ]
    return await _limited(
        limiter,
        rules,
        lambda: service.student_join(
            session,
            join_code=body.join_code,
            display_name=body.display_name,
            last_name=body.last_name,
            pin=body.pin,
            settings=settings,
        ),
    )


@router.post(
    "/classes/{class_id}/students/{student_id}/pin-reset",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**R401, **R403, **R404},
)
async def pin_reset(klass: StaffClass, student_id: uuid.UUID, session: Session) -> Response:
    """Скидає PIN учня (вчитель цього класу або адмін школи): наступний вхід задасть новий.
    Усі сесії учня (access- і refresh-токени) перестають діяти."""
    await service.reset_student_pin(session, klass, student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/students/{student_id}/parent-link-codes",
    response_model=ParentLinkCodeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**R401, **R403, **R404},
)
async def create_parent_link_code(
    staff: Staff, student: AccessibleStudent, session: Session, settings: SettingsDep
) -> ParentLinkCodeResponse:
    """Одноразовий код для прив'язки батьків до дитини (7 днів)."""
    code, expires_at = await service.create_parent_link_code(session, staff, student, settings)
    return ParentLinkCodeResponse(code=code, expires_at=expires_at)


@router.post(
    "/parent/link",
    response_model=ParentLinkResponse,
    responses={
        400: {"model": ErrorResponse, "description": "INVALID_LINK_CODE"},
        **R401,
        **R403,
    },
)
async def parent_link(body: ParentLinkRequest, parent: Parent, session: Session):
    """Прив'язує батьків до дитини за кодом від вчителя. Повторний виклик ідемпотентний."""
    child = await service.link_parent(session, parent, body.code)
    return ParentLinkResponse(
        child_id=child.id, display_name=child.display_name, last_name=child.last_name
    )


@router.post(
    "/admin/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"model": ErrorResponse, "description": "EMAIL_TAKEN"},
        **R401,
        **R403,
    },
)
async def admin_create_user(body: AdminCreateUserRequest, admin: Admin, session: Session):
    """Адмін створює вчителя, батьків або адміна у своїй школі. Самореєстрації немає."""
    if admin.school_id is None:
        raise AppError("FORBIDDEN", "Admin is not attached to a school", status_code=403)
    user = await service.create_account(
        session,
        role=body.role,
        email=body.email,
        display_name=body.display_name,
        last_name=body.last_name,
        password=body.password,
        school_id=admin.school_id,
    )
    return UserOut.model_validate(user)


@router.get("/admin/users", response_model=list[UserOut], responses={**R401, **R403})
async def admin_list_users(
    admin: Admin,
    session: Session,
    role: Annotated[Literal["teacher", "admin", "student"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserOut]:
    """Активні користувачі школи адміна (напр. `?role=teacher` для призначення на клас),
    за прізвищем та ім'ям. Батьки до школи не прив'язані й тут не показуються."""
    if admin.school_id is None:
        raise AppError("FORBIDDEN", "Admin is not attached to a school", status_code=403)
    users = await school_service.list_school_users(session, admin.school_id, role, limit, offset)
    return [UserOut.model_validate(u) for u in users]
