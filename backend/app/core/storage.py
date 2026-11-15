"""Сховище медіафайлів. Зараз — локальний каталог (том Docker, роздає Nginx);
інтерфейс MediaStorage дозволяє пізніше підставити об'єктне сховище (S3)."""

import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from pathlib import Path, PurePosixPath

import anyio


class MediaStorage(ABC):
    @abstractmethod
    async def save(self, key: str, chunks: AsyncIterable[bytes]) -> None:
        """Записує потік під ключем. Файл з'являється під ключем лише цілим (атомарно);
        якщо потік обірвався чи кинув помилку — нічого не лишається."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Видаляє об'єкт; відсутній об'єкт — не помилка."""

    @abstractmethod
    def url(self, key: str) -> str:
        """Публічний URL об'єкта (його кешує Service Worker)."""


class LocalMediaStorage(MediaStorage):
    def __init__(self, root: str | Path, url_prefix: str) -> None:
        # Корінь створюємо й розв'язуємо один раз: на Windows resolve() шляху, каталоги якого
        # саме створюють паралельні завантаження, інколи повертає інше написання шляху.
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.url_prefix = url_prefix.rstrip("/")

    def _path(self, key: str) -> Path:
        # Ключі генерує сервер, але все одно не випускаємо шлях за межі кореня.
        parts = PurePosixPath(key).parts
        # «:» і «\» відсікають диски й розділювачі Windows (C:, ..\) у частинах ключа.
        if not parts or any(
            p in (".", "..", "") or p.startswith("/") or ":" in p or "\\" in p for p in parts
        ):
            raise ValueError("Invalid storage key")
        # Шлях будуємо від уже розв'язаного кореня без resolve(): «..» та абсолютні частини
        # відкинуто вище, тож лексична перевірка достатня.
        path = self.root.joinpath(*parts)
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid storage key")
        return path

    async def save(self, key: str, chunks: AsyncIterable[bytes]) -> None:
        path = self._path(key)
        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
        try:
            async with await anyio.open_file(tmp, "wb") as f:
                async for chunk in chunks:
                    await f.write(chunk)
            await anyio.to_thread.run_sync(os.replace, tmp, path)
        except BaseException:
            await anyio.Path(tmp).unlink(missing_ok=True)
            raise

    async def delete(self, key: str) -> None:
        await anyio.Path(self._path(key)).unlink(missing_ok=True)

    def url(self, key: str) -> str:
        return f"{self.url_prefix}/{key}"
