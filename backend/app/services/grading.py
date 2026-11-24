"""Перевірка відповіді на одне питання тесту (спроби з синхронізації, переоцінка, агрегати).

Питання зараховане лише повністю правильною відповіддю, часткових балів немає:
- `single` / `multiple` — множина обраних id дорівнює ключу;
- `text` — одна введена відповідь, що після нормалізації (`normalize_text`) збігається
  з однією з прийнятних;
- `match` — пари `{лівий: правий}` дорівнюють ключу повністю.

Відповідь не того формату (наприклад, список для `match`) — просто неправильна: спроба
зберігається, переоцінка після зміни типу питання дає коректний результат.
"""

import re
import unicodedata
from typing import Any

# Різні апострофи (українська клавіатура, автозаміна) — один символ.
_APOSTROPHES = str.maketrans({c: "'" for c in "’ʼ‘`´ʹ′‛"})
_SPACES = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Для порівняння короткої відповіді: апострофи → ', NFKC, пробіли по краях прибрано,
    кілька пробілів поспіль → один, без різниці регістру."""
    value = unicodedata.normalize("NFKC", value.translate(_APOSTROPHES))
    return _SPACES.sub(" ", value).strip().casefold()


def is_correct(kind: str, key: Any, answer: Any) -> bool:
    """Чи зараховане питання. `answer` — значення з `answers` спроби (None — без відповіді)."""
    if not key or answer is None:
        return False
    if kind == "text":
        if not isinstance(answer, list) or len(answer) != 1 or not isinstance(answer[0], str):
            return False
        given = normalize_text(answer[0])
        return bool(given) and given in {normalize_text(k) for k in key}
    if kind == "match":
        return isinstance(answer, dict) and isinstance(key, dict) and answer == key
    if not isinstance(answer, list) or not isinstance(key, list):
        return False
    return set(answer) == set(key)
