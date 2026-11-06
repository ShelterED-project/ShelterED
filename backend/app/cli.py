"""Адміністративні команди: python -m app.cli create-admin --email ... --name ... --school-id ...

Також: python -m app.cli export-openapi (записує docs/openapi.json),
python -m app.cli gen-vapid (друкує нову пару ключів VAPID для Web Push),
python -m app.cli seed (демо-дані; пароль дорослих — SEED_PASSWORD або згенерований).
"""

import argparse
import asyncio
import base64
import copy
import getpass
import json
import os
import sys
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import TypeAdapter, ValidationError

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.errors import AppError
from app.models.school import School
from app.schemas.auth import Email, Name
from app.services.auth import create_account


async def create_admin(
    email: str, name: str, last_name: str | None, school_id: uuid.UUID, password: str
) -> uuid.UUID:
    async with get_sessionmaker()() as session:
        if await session.get(School, school_id) is None:
            raise AppError("NOT_FOUND", "School not found", status_code=404)
        user = await create_account(
            session,
            role="admin",
            email=email,
            display_name=name,
            last_name=last_name,
            password=password,
            school_id=school_id,
        )
        return user.id


OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


OPENAPI_TITLE = "ShelterED API"


def render_openapi() -> str:
    """Специфікація API у стабільному вигляді (відсортовані ключі), щоб diff був змістовним."""
    # Для генерації специфікації секрет не потрібен, але Settings вимагає його при імпорті.
    os.environ.setdefault("JWT_SECRET", "openapi-export-placeholder")
    from app.main import app

    spec = copy.deepcopy(app.openapi())
    # Назва залежить від APP_NAME, тож у файлі вона фіксована (специфікація не залежить від env).
    spec["info"]["title"] = OPENAPI_TITLE
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def gen_vapid() -> tuple[str, str]:
    """Нова пара ключів VAPID (P-256): публічний — нестиснена точка (applicationServerKey для
    `pushManager.subscribe`), приватний — 32 байти; обидва base64url без `=`."""
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    private = key.private_numbers().private_value.to_bytes(32, "big")
    return _b64url(public), _b64url(private)


def run_seed() -> int:
    """Демо-дані в БД з DATABASE_URL. Пароль дорослих — SEED_PASSWORD, інакше генерується й
    друкується один раз (лише при створенні акаунтів); у репозиторії паролів немає."""
    from app.seed.content import STUDENT_PIN
    from app.seed.runner import SeedRefused, seed

    settings = get_settings()
    if settings.environment == "prod":
        print("Error: seed data is not allowed when ENVIRONMENT=prod", file=sys.stderr)
        return 1
    # Із Settings: змінна оточення або `.env` (SecretStr — у repr/логи не потрапляє).
    secret = settings.seed_password
    password = (secret.get_secret_value() if secret else None) or None
    if password is not None and len(password) < 8:
        print("SEED_PASSWORD must be at least 8 characters", file=sys.stderr)
        return 1

    async def run():
        try:
            async with get_sessionmaker()() as session:
                return await seed(session, settings, password=password)
        finally:
            await get_engine().dispose()

    try:
        result = asyncio.run(run())
    except SeedRefused as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"School: {result.school_id}")
    for name, code in result.join_codes.items():
        print(f"Class {name}: join code {code}, students' PIN {STUDENT_PIN}")
    print("Adults: " + ", ".join(result.adult_emails))
    if result.generated_password:
        print(f"Adults' password (shown once): {result.generated_password}")
    elif result.passwords_set:
        print("Adults' password: from SEED_PASSWORD")
    else:
        print("Adults' passwords unchanged (set SEED_PASSWORD to reset)")
    print(f"Lessons: {result.lessons}, new packs: {result.packs_built}")
    if result.problems:
        print(f"Publication checks failed: {result.problems}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Створити першого адміна школи")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True, help="Імʼя")
    p.add_argument("--last-name")
    p.add_argument("--school-id", required=True, type=uuid.UUID)
    p.add_argument("--password", help="Для скриптів; інакше буде запит")
    sub.add_parser("export-openapi", help="Записати docs/openapi.json зі специфікації FastAPI")
    sub.add_parser("gen-vapid", help="Надрукувати нову пару ключів VAPID (у .env не пише)")
    sub.add_parser("seed", help="Демо-дані: школа, класи, люди, розклад, уроки, пакети")
    args = parser.parse_args(argv)

    if args.command == "seed":
        return run_seed()

    if args.command == "gen-vapid":
        # Лише в stdout: ключ не пишеться у файли й не потрапляє в логи.
        public, private = gen_vapid()
        print(f"VAPID_PUBLIC_KEY={public}")
        print(f"VAPID_PRIVATE_KEY={private}")
        print("VAPID_SUBJECT=mailto:<admin email>")
        return 0

    if args.command == "export-openapi":
        OPENAPI_PATH.write_text(render_openapi(), encoding="utf-8", newline="\n")
        print(f"Written: {OPENAPI_PATH}")
        return 0

    password = args.password
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match", file=sys.stderr)
            return 1
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 1
    try:
        email = TypeAdapter(Email).validate_python(args.email)
        name = TypeAdapter(Name).validate_python(args.name)
        last_name = TypeAdapter(Name).validate_python(args.last_name) if args.last_name else None
    except ValidationError as exc:
        print(
            f"Invalid argument: {exc.errors()[0]['loc']} {exc.errors()[0]['msg']}", file=sys.stderr
        )
        return 1

    async def run() -> uuid.UUID:
        try:
            return await create_admin(email, name, last_name, args.school_id, password)
        finally:
            await get_engine().dispose()

    try:
        user_id = asyncio.run(run())
    except AppError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    print(f"Admin created: {user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
