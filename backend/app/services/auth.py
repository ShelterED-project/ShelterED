import datetime as dt
import re
import unicodedata
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_secret_async,
    hash_token,
    new_link_code,
    new_opaque_token,
    normalize_link_code,
    verify_pkce,
    verify_secret_async,
)
from app.models.auth import AuthCode, ParentLinkCode, RefreshToken
from app.models.school import ClassMembership, ParentChild, SchoolClass, User
from app.schemas.auth import TokenResponse


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _invalid_credentials() -> AppError:
    return AppError("INVALID_CREDENTIALS", "Invalid credentials", status_code=401)


def _invalid_grant() -> AppError:
    return AppError("INVALID_GRANT", "Invalid or expired grant", status_code=400)


def _invalid_join_code() -> AppError:
    return AppError("INVALID_JOIN_CODE", "Invalid or expired class code", status_code=400)


def _email_taken() -> AppError:
    return AppError("EMAIL_TAKEN", "Email is already registered", status_code=409)


def _join_code_expired(klass) -> bool:
    return bool(klass.join_code_expires_at and klass.join_code_expires_at <= _now())


async def _lock_user(session: AsyncSession, user: User) -> None:
    """Блокує рядок користувача (FOR NO KEY UPDATE) і перечитує його."""
    await session.refresh(user, with_for_update={"key_share": True})


# ---------- токени ----------


async def issue_tokens(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    family_id: uuid.UUID | None = None,
) -> tuple[TokenResponse, RefreshToken]:
    """Видає пару токенів. Commit робить викликач."""
    raw = new_opaque_token()
    row = RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_token(raw),
        expires_at=_now() + dt.timedelta(days=settings.refresh_token_ttl_days),
        token_version=user.token_version,
    )
    session.add(row)
    await session.flush()
    response = TokenResponse(
        access_token=create_access_token(user.id, user.role, settings, user.token_version),
        refresh_token=raw,
        expires_in=settings.access_token_ttl_min * 60,
    )
    return response, row


async def _revoke_tokens(session: AsyncSession, *criteria) -> None:
    """Відкликає (revoked_at) усі ще не відкликані refresh-токени, що підпадають під критерії."""
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_(None), *criteria)
        .values(revoked_at=_now())
    )


async def refresh_tokens(
    session: AsyncSession, raw_token: str, settings: Settings
) -> TokenResponse:
    """Ротація refresh-токена.

    Відкликаний токен (вихід, скидання PIN, відкликана родина) завжди дає INVALID_GRANT.
    Уже ротований токен у межах refresh_reuse_grace_seconds вважається повтором (втрачена
    відповідь, дві вкладки), якщо найновіший виданий з нього токен ще не використано:
    видаємо нову пару в тій самій родині. Інакше це повторне використання, тож відкликаємо
    всю родину (можлива крадіжка).
    """
    row = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update(key_share=True)
    )
    if row is None or row.revoked_at is not None:
        raise _invalid_grant()
    now = _now()
    if row.rotated_at is not None:
        successor = (
            await session.scalar(
                select(RefreshToken)
                .where(RefreshToken.id == row.replaced_by_id)
                .with_for_update(key_share=True)
            )
            if row.replaced_by_id is not None
            else None
        )
        grace = dt.timedelta(seconds=settings.refresh_reuse_grace_seconds)
        if (
            successor is None
            or successor.rotated_at is not None
            or successor.revoked_at is not None
            or now - row.rotated_at > grace
        ):
            await _revoke_tokens(session, RefreshToken.family_id == row.family_id)
            await session.commit()
            raise _invalid_grant()
    user = await session.get(User, row.user_id)
    if (
        row.expires_at <= now
        or user is None
        or not user.is_active
        or user.token_version != row.token_version
    ):
        raise _invalid_grant()
    response, new_row = await issue_tokens(session, user, settings, family_id=row.family_id)
    # Повтор лишає токен «ротованим» з початковим часом; перша ротація ставить час.
    row.replaced_by_id = new_row.id
    if row.rotated_at is None:
        row.rotated_at = now
    await session.commit()
    return response


async def logout(session: AsyncSession, raw_token: str) -> None:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    if row is not None:
        await _revoke_tokens(session, RefreshToken.family_id == row.family_id)
        await session.commit()


# ---------- OAuth 2.0 Authorization Code + PKCE ----------


async def authorize(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    code_challenge: str,
    client_id: str,
    redirect_uri: str | None,
    settings: Settings,
) -> str:
    if client_id not in settings.oauth_client_ids:
        raise AppError("INVALID_CLIENT", "Unknown client_id", status_code=400)
    if redirect_uri is not None and redirect_uri not in settings.oauth_redirect_uris:
        raise AppError("INVALID_REDIRECT_URI", "redirect_uri is not allowed", status_code=400)
    user = await session.scalar(select(User).where(User.email == email))
    # verify_secret_async з None виконує фіктивну перевірку: час відповіді не видає, чи існує email.
    # Захист від підбору пароля — rate limiting невдалих спроб у роутері (app/core/rate_limit.py),
    # а не блокування акаунтів (діти могли б навмисно блокувати інших).
    password_ok = await verify_secret_async(password, user.password_hash if user else None)
    if user is None or not user.is_active or not password_ok:
        raise _invalid_credentials()
    code = new_opaque_token()
    session.add(
        AuthCode(
            code_hash=hash_token(code),
            user_id=user.id,
            code_challenge=code_challenge,
            client_id=client_id,
            redirect_uri=redirect_uri,
            expires_at=_now() + dt.timedelta(seconds=settings.auth_code_ttl_s),
        )
    )
    await session.commit()
    return code


async def exchange_code(
    session: AsyncSession,
    *,
    code: str,
    code_verifier: str,
    client_id: str,
    redirect_uri: str | None,
    settings: Settings,
) -> TokenResponse:
    row = await session.scalar(
        select(AuthCode).where(AuthCode.code_hash == hash_token(code)).with_for_update()
    )
    if row is None or row.used_at is not None:
        raise _invalid_grant()
    # Код спалюється при першій спробі, навіть невдалій.
    row.used_at = _now()
    await session.commit()
    if (
        row.expires_at <= _now()
        or row.client_id != client_id
        or row.redirect_uri != redirect_uri
        or not verify_pkce(code_verifier, row.code_challenge)
    ):
        raise _invalid_grant()
    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise _invalid_grant()
    response, _ = await issue_tokens(session, user, settings)
    await session.commit()
    return response


# ---------- вхід учня ----------


_APOSTROPHES = re.compile("[\u2019\u02bc\u2018`]")
MAX_NAME_LENGTH = 50


def clean_name(value: str) -> str:
    """Імʼя для збереження: NFKC, єдиний апостроф, один пробіл між словами, без країв."""
    value = unicodedata.normalize("NFKC", value)
    return " ".join(_APOSTROPHES.sub("'", value).split())


def name_key(display_name: str, last_name: str) -> str:
    """Ключ пошуку учня. Рахується в Python: lower() у PostgreSQL залежить від локалі БД.

    Роздільник \t не може бути в очищеному імені (clean_name замінює його пробілом).
    """
    return f"{clean_name(display_name).casefold()}\t{clean_name(last_name).casefold()}"


def _checked_name(value: str) -> str:
    cleaned = clean_name(value)
    if not 1 <= len(cleaned) <= MAX_NAME_LENGTH:
        raise AppError("VALIDATION_ERROR", "Invalid name", status_code=422)
    return cleaned


async def _find_student(session: AsyncSession, class_id: uuid.UUID, key: str) -> User | None:
    return await session.scalar(
        select(User)
        .options(load_only(User.id, User.role, User.is_active, User.pin_hash, User.token_version))
        .join(ClassMembership, ClassMembership.user_id == User.id)
        .where(
            ClassMembership.class_id == class_id,
            ClassMembership.member_role == "student",
            User.name_key == key,
        )
        .order_by(User.created_at, User.id)
        .limit(1)
    )


async def _login_existing_student(
    session: AsyncSession, student: User, pin: str, settings: Settings
) -> TokenResponse:
    if not student.is_active:
        raise _invalid_credentials()
    pin_hash, version = student.pin_hash, student.token_version
    # argon2 рахуємо до блокування рядка.
    # TODO: захист від підбору PIN — rate limiting запитів в епіку безпеки, а не блокування
    # акаунтів учнів.
    if pin_hash is not None and not await verify_secret_async(pin, pin_hash):
        raise _invalid_credentials()
    # PIN скинув вчитель (NULL): перший вхід задає новий.
    new_hash = await hash_secret_async(pin) if pin_hash is None else None
    # Під блокуванням перевіряємо, що PIN чи епоха не змінилися за час перевірки
    # (паралельне скидання PIN не має дати токени).
    await _lock_user(session, student)
    if not student.is_active or student.token_version != version:
        raise _invalid_credentials()
    if student.pin_hash != pin_hash:
        # Допустимо лише паралельний перший вхід, що вже задав PIN: він має збігатися з нашим.
        if pin_hash is not None or not await verify_secret_async(pin, student.pin_hash):
            raise _invalid_credentials()
    elif pin_hash is None:
        student.pin_hash = new_hash
    response, _ = await issue_tokens(session, student, settings)
    await session.commit()
    return response


async def student_join(
    session: AsyncSession,
    *,
    join_code: str,
    display_name: str,
    last_name: str,
    pin: str,
    settings: Settings,
    before_create: Callable[[uuid.UUID], Awaitable[None]] | None = None,
) -> TokenResponse:
    """`before_create(class_id)` викликається лише перед створенням нового учня (не для входу
    наявного): там API рахує ліміт нових учнів і може кинути 429."""
    # Код класу зберігається у нормалізованому вигляді (normalize_link_code).
    code = normalize_link_code(join_code)
    klass = await session.scalar(
        select(SchoolClass)
        .options(load_only(SchoolClass.id, SchoolClass.school_id, SchoolClass.join_code_expires_at))
        .where(SchoolClass.join_code == code)
    )
    if klass is None:
        raise _invalid_join_code()
    display_name, last_name = _checked_name(display_name), _checked_name(last_name)
    key = name_key(display_name, last_name)
    class_id, school_id = klass.id, klass.school_id

    # Наявний учень входить і після завершення терміну коду: він лише обмежує створення нових.
    student = await _find_student(session, class_id, key)
    if student is not None:
        return await _login_existing_student(session, student, pin, settings)
    if _join_code_expired(klass):
        # Той самий 401, що й для хибного PIN: не розкриваємо, які імена є в класі.
        await verify_secret_async(pin, None)
        raise _invalid_credentials()
    if before_create is not None:
        await before_create(class_id)

    # Хеш рахуємо до блокування: argon2 повільний, а блокування тримає всіх, хто входить у клас.
    pin_hash = await hash_secret_async(pin)
    # FOR NO KEY UPDATE: перші входи в один клас ідуть по черзі, тож два одночасні входи
    # з тим самим ім'ям не створять двох учнів. Код перевіряємо знову: його могли змінити.
    klass = await session.scalar(
        select(SchoolClass)
        .where(SchoolClass.id == class_id, SchoolClass.join_code == code)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if klass is None:
        raise _invalid_join_code()
    student = await _find_student(session, class_id, key)
    if student is not None:
        # Паралельний запит встиг створити учня: звільняємо блокування класу (commit) до argon2.
        await session.commit()
        return await _login_existing_student(session, student, pin, settings)
    if _join_code_expired(klass):
        raise _invalid_credentials()

    student = User(
        role="student",
        display_name=display_name,
        last_name=last_name,
        name_key=key,
        school_id=school_id,
        pin_hash=pin_hash,
    )
    session.add(student)
    await session.flush()
    session.add(ClassMembership(class_id=class_id, user_id=student.id, member_role="student"))
    response, _ = await issue_tokens(session, student, settings)
    await session.commit()
    return response


async def reset_student_pin(
    session: AsyncSession, klass: SchoolClass, student_id: uuid.UUID
) -> None:
    student = await session.scalar(
        select(User)
        .join(ClassMembership, ClassMembership.user_id == User.id)
        .where(
            User.id == student_id,
            User.role == "student",
            ClassMembership.class_id == klass.id,
            ClassMembership.member_role == "student",
        )
        .with_for_update(key_share=True, of=User)
    )
    if student is None:
        raise AppError("NOT_FOUND", "Student not found in this class", status_code=404)
    student.pin_hash = None
    # Нова епоха: живі access-токени й refresh-токени, видані раніше (зокрема паралельними
    # входами), перестають діяти. PIN могли скинути через компрометацію.
    student.token_version += 1
    await _revoke_tokens(session, RefreshToken.user_id == student.id)
    await session.commit()


# ---------- акаунти дорослих ----------


async def create_account(
    session: AsyncSession,
    *,
    role: str,
    email: str,
    display_name: str,
    last_name: str | None,
    password: str,
    school_id: uuid.UUID | None,
) -> User:
    if await session.scalar(select(User.id).where(User.email == email)):
        raise _email_taken()
    user = User(
        role=role,
        email=email,
        display_name=display_name,
        last_name=last_name,
        password_hash=await hash_secret_async(password),
        # Батьки не належать школі (школа дитини визначається через parent_child).
        school_id=None if role == "parent" else school_id,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # Лише порушення унікальності email (паралельний запит) дає 409; решту не маскуємо.
        if "uq_app_user_email" not in str(exc.orig):
            raise
        raise _email_taken() from exc
    return user


# ---------- прив'язка батьків ----------


async def create_parent_link_code(
    session: AsyncSession, creator: User, student: User, settings: Settings
) -> tuple[str, dt.datetime]:
    code = new_link_code()
    expires_at = _now() + dt.timedelta(days=settings.parent_link_code_ttl_days)
    session.add(
        ParentLinkCode(
            code_hash=hash_token(code),
            child_id=student.id,
            created_by=creator.id,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return code, expires_at


async def link_parent(session: AsyncSession, parent: User, raw_code: str) -> User:
    row = await session.scalar(
        select(ParentLinkCode)
        .where(ParentLinkCode.code_hash == hash_token(normalize_link_code(raw_code)))
        .with_for_update()
    )
    invalid = AppError("INVALID_LINK_CODE", "Invalid or expired code", status_code=400)
    if row is None:
        raise invalid
    # Повторне введення свого ж коду — ідемпотентне.
    if row.used_at is not None and row.used_by != parent.id:
        raise invalid
    if row.used_at is None and row.expires_at <= _now():
        raise invalid
    child = await session.get(User, row.child_id)
    if child is None or not child.is_active:
        raise invalid
    if await session.get(ParentChild, (parent.id, child.id)) is None:
        session.add(ParentChild(parent_id=parent.id, child_id=child.id))
    if row.used_at is None:
        row.used_at = _now()
        row.used_by = parent.id
    await session.commit()
    return child


# ---------- перевірки доступу (за роллю та належністю) ----------


async def get_class(session: AsyncSession, class_id: uuid.UUID) -> SchoolClass | None:
    return await session.get(SchoolClass, class_id)


async def is_member(
    session: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID, member_role: str
) -> bool:
    found = await session.scalar(
        select(ClassMembership.user_id).where(
            ClassMembership.user_id == user_id,
            ClassMembership.class_id == class_id,
            ClassMembership.member_role == member_role,
        )
    )
    return found is not None


async def can_access_class(session: AsyncSession, user: User, klass: SchoolClass) -> bool:
    """Вчитель — лише свої класи, учень — свій, адмін — класи своєї школи, батьки — жодних."""
    if user.role == "admin":
        return user.school_id is not None and klass.school_id == user.school_id
    if user.role in ("teacher", "student"):
        return await is_member(session, user.id, klass.id, user.role)
    return False


async def can_access_student(session: AsyncSession, user: User, student: User) -> bool:
    """Учень — лише себе, батьки — лише прив'язаних дітей, вчитель — учнів своїх класів."""
    if user.role == "student":
        return user.id == student.id
    if user.role == "parent":
        return await session.get(ParentChild, (user.id, student.id)) is not None
    if user.role == "admin":
        return user.school_id is not None and student.school_id == user.school_id
    if user.role == "teacher":
        mine = select(ClassMembership.class_id).where(
            ClassMembership.user_id == user.id, ClassMembership.member_role == "teacher"
        )
        found = await session.scalar(
            select(ClassMembership.user_id).where(
                ClassMembership.user_id == student.id,
                ClassMembership.member_role == "student",
                ClassMembership.class_id.in_(mine),
            )
        )
        return found is not None
    return False
