import datetime as dt
import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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


# ---------- токени ----------


async def issue_tokens(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    family_id: uuid.UUID | None = None,
    user_agent: str | None = None,
) -> tuple[TokenResponse, RefreshToken]:
    """Видає пару токенів. Commit робить викликач."""
    raw = new_opaque_token()
    row = RefreshToken(
        user_id=user.id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_token(raw),
        expires_at=_now() + dt.timedelta(days=settings.refresh_token_ttl_days),
        user_agent=user_agent[:200] if user_agent else None,
    )
    session.add(row)
    await session.flush()
    response = TokenResponse(
        access_token=create_access_token(user.id, user.role, settings),
        refresh_token=raw,
        expires_in=settings.access_token_ttl_min * 60,
    )
    return response, row


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def refresh_tokens(
    session: AsyncSession, raw_token: str, settings: Settings, user_agent: str | None = None
) -> TokenResponse:
    """Ротація refresh-токена. Повторне пред'явлення вже використаного відкликає всю родину,
    крім повтору в межах refresh_reuse_grace_seconds (втрачена відповідь)."""
    row = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if row is None:
        raise _invalid_grant()
    now = _now()
    retry_of: RefreshToken | None = None
    if row.revoked_at is not None:
        # Токен уже ротовано або відкликано. Якщо це сталося щойно, а наступник ще не
        # використано, клієнт, імовірно, не отримав відповіді (обрив мережі) і повторює запит.
        successor = (
            await session.scalar(
                select(RefreshToken).where(RefreshToken.id == row.replaced_by_id).with_for_update()
            )
            if row.replaced_by_id is not None
            else None
        )
        grace = dt.timedelta(seconds=settings.refresh_reuse_grace_seconds)
        if successor is not None and successor.revoked_at is None and now - row.revoked_at <= grace:
            retry_of = successor
        else:
            # Токен могли вкрасти.
            await _revoke_family(session, row.family_id)
            await session.commit()
            raise _invalid_grant()
    user = await session.get(User, row.user_id)
    if row.expires_at <= now or user is None or not user.is_active:
        raise _invalid_grant()
    response, new_row = await issue_tokens(
        session, user, settings, family_id=row.family_id, user_agent=user_agent
    )
    if retry_of is not None:
        # Повтор: токен із загубленої відповіді клієнту невідомий, тож відкликаємо його.
        retry_of.revoked_at = now
        retry_of.replaced_by_id = new_row.id
    else:
        row.revoked_at = now
        row.replaced_by_id = new_row.id
    await session.commit()
    return response


async def logout(session: AsyncSession, raw_token: str) -> None:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    if row is not None:
        await _revoke_family(session, row.family_id)
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
    user = await session.scalar(select(User).where(User.email == email))
    # verify_secret_async з None виконує фіктивну перевірку: час відповіді не видає, чи існує email.
    # TODO: захист від підбору пароля — rate limiting запитів (за клієнтом/IP) в епіку безпеки,
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
    user_agent: str | None = None,
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
    response, _ = await issue_tokens(session, user, settings, user_agent=user_agent)
    await session.commit()
    return response


# ---------- вхід учня ----------


_APOSTROPHES = re.compile("[\u2019\u02bc\u2018`]")


def clean_name(value: str) -> str:
    """Імʼя для збереження: єдиний апостроф, один пробіл між словами, без пробілів по краях."""
    return " ".join(_APOSTROPHES.sub("'", value).split())


def name_key(value: str) -> str:
    """Ключ порівняння імен. Порівнюємо в Python: lower() у PostgreSQL залежить від локалі БД."""
    return clean_name(value).casefold()


async def _find_student(
    session: AsyncSession, class_id: uuid.UUID, display_name: str, last_name: str
) -> User | None:
    key = (name_key(display_name), name_key(last_name))
    students = await session.scalars(
        select(User)
        .join(ClassMembership, ClassMembership.user_id == User.id)
        .where(ClassMembership.class_id == class_id, ClassMembership.member_role == "student")
    )
    return next(
        (s for s in students if (name_key(s.display_name), name_key(s.last_name or "")) == key),
        None,
    )


async def _login_existing_student(
    session: AsyncSession, student: User, pin: str, settings: Settings, user_agent: str | None
) -> TokenResponse:
    if not student.is_active:
        raise _invalid_credentials()
    if student.pin_hash is None:
        # PIN скинув вчитель: перший вхід задає новий.
        new_hash = await hash_secret_async(pin)
        await session.refresh(student, with_for_update=True)
        if student.pin_hash is None:
            student.pin_hash = new_hash
        elif not await verify_secret_async(pin, student.pin_hash):
            raise _invalid_credentials()
    # TODO: захист від підбору PIN — rate limiting запитів (за клієнтом/IP) в епіку
    # безпеки, а не блокування акаунтів учнів.
    elif not await verify_secret_async(pin, student.pin_hash):
        raise _invalid_credentials()
    response, _ = await issue_tokens(session, student, settings, user_agent=user_agent)
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
    user_agent: str | None = None,
) -> TokenResponse:
    # Код класу зберігається у нормалізованому вигляді (normalize_link_code).
    code = normalize_link_code(join_code)
    invalid_code = AppError("INVALID_JOIN_CODE", "Invalid or expired class code", status_code=400)
    klass = await session.scalar(select(SchoolClass).where(SchoolClass.join_code == code))
    if klass is None:
        raise invalid_code
    display_name, last_name = clean_name(display_name), clean_name(last_name)

    # Наявний учень входить і після завершення терміну коду: він лише обмежує створення нових.
    student = await _find_student(session, klass.id, display_name, last_name)
    if student is not None:
        return await _login_existing_student(session, student, pin, settings, user_agent)

    if klass.join_code_expires_at and klass.join_code_expires_at <= _now():
        raise invalid_code

    # Хеш рахуємо до блокування: argon2 повільний, а блокування тримає всіх, хто входить у клас.
    pin_hash = await hash_secret_async(pin)
    # FOR UPDATE: перші входи в один клас ідуть по черзі, тож два одночасні входи
    # з тим самим ім'ям (подвійне натискання, повтор запиту) не створять двох учнів.
    klass = await session.scalar(
        select(SchoolClass)
        .where(SchoolClass.id == klass.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if klass is None or (klass.join_code_expires_at and klass.join_code_expires_at <= _now()):
        raise invalid_code
    student = await _find_student(session, klass.id, display_name, last_name)
    if student is not None:
        # Паралельний запит встиг створити учня: це вже вхід (commit звільняє блокування).
        return await _login_existing_student(session, student, pin, settings, user_agent)

    student = User(
        role="student",
        display_name=display_name,
        last_name=last_name,
        school_id=klass.school_id,
        pin_hash=pin_hash,
    )
    session.add(student)
    await session.flush()
    session.add(ClassMembership(class_id=klass.id, user_id=student.id, member_role="student"))
    response, _ = await issue_tokens(session, student, settings, user_agent=user_agent)
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
    )
    if student is None:
        raise AppError("NOT_FOUND", "Student not found in this class", status_code=404)
    student.pin_hash = None
    # Старі сесії учня (усі родини) недійсні: PIN могли скинути через компрометацію.
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == student.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
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
        raise AppError("EMAIL_TAKEN", "Email is already registered", status_code=409)
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
        # Паралельний запит зайняв email між перевіркою й вставкою.
        await session.rollback()
        raise AppError("EMAIL_TAKEN", "Email is already registered", status_code=409) from exc
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
