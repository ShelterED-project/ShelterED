import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from app.config import settings


logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM недоступна або повернула непридатну відповідь (HTTP 503)."""


_client: Optional[OpenAI] = None
_THINK = re.compile(r"<think>.*?</think>", re.S)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.AI_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT,
            max_retries=0,
        )
    return _client


def _model(kind: str) -> str:
    if kind == "fast":
        return settings.MODEL_FAST or settings.MODELS
    elif kind == "ocr":
        return settings.MODEL_OCR or settings.MODELS
    return settings.MODEL_EXPLAIN or settings.MODELS


def complete(
    system: str,
    user: str,
    *,
    kind: str = "explain",
    history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 0.4,
    max_tokens: int = 500,
    mock: str = "[MOCK] відповідь",
    timeout: Optional[float] = None,
) -> str:
    if settings.MOCK_LLM:
        return mock

    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    for m in (history or [])[-8:]:
        if hasattr(m, "model_dump"):  # HistoryItem
            m = m.model_dump()
        role = m.get("role")
        text = m.get("text") or m.get("content")
        if role in ("user", "assistant") and text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": user})

    try:
        r = _get_client().chat.completions.create(
            model=_model(kind),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout or settings.LLM_TIMEOUT,
        )
        text = r.choices[0].message.content or ""
    except Exception as e:  # мережа, таймаут, 5xx
        raise LLMError(str(e)) from e

    text = _THINK.sub("", text).strip()   # deepseek-r1 повертає <think>...</think>
    if not text:
        raise LLMError("empty response")
    return text


def _repair_json(text: str) -> str:
    """Типові помилки JSON від LLM (MamayLM/Gemma, Llama). Вміст рядків не чіпаємо.

    - кома перед `}` / `]`;
    - коментарі `//` і `/* */`;
    - зайва `{` там, де очікується ключ: `{"m1": {...}}, {"m2": {...}}` — модель закрила
      об'єкт і продовжила новими `{...}` через кому. Такі `{` і парні їм `}` прибираємо,
      ключі опиняються в батьківському об'єкті (analysis.py переносить `m2…` куди треба);
    - не закриті наприкінці дужки (відповідь обрізана) — дописуємо."""
    out: List[str] = []
    stack: List[str] = []  # "{", "[" або "skip" (прибрана зайва `{`)
    expect_key = False
    i, n, in_str = 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue
            if c == '"':
                in_str = False
            out.append(c)
        elif c == '"':
            in_str = True
            expect_key = False
            out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        elif c == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1  # кома перед закриваючою дужкою
                continue
            expect_key = bool(stack) and stack[-1] in ("{", "skip")
            out.append(c)
        elif c == "{":
            if expect_key:
                stack.append("skip")  # зайва `{` на місці ключа
            else:
                stack.append("{")
                out.append(c)
                expect_key = True
        elif c == "[":
            stack.append("[")
            out.append(c)
            expect_key = False
        elif c in "}]":
            top = stack.pop() if stack else None
            if top != "skip":
                out.append(c)
            expect_key = False
        else:
            if c not in " \t\r\n":
                expect_key = False
            out.append(c)
        i += 1
    if in_str:
        out.append('"')
    for top in reversed(stack):
        if top != "skip":
            out.append("}" if top == "{" else "]")
    return "".join(out)


def _extract_json(raw: str) -> Dict[str, Any]:
    """Перший JSON-об'єкт у відповіді: без markdown-огорожі й тексту до/після нього. Якщо
    звичайний розбір не вдався — ще раз після `_repair_json`."""
    start = raw.find("{")
    if start == -1:
        raise ValueError("no JSON object")
    decoder = json.JSONDecoder(strict=False)  # сирі переноси рядків усередині рядків
    try:
        data, _ = decoder.raw_decode(raw, start)
    except json.JSONDecodeError as first:
        try:
            data, _ = decoder.raw_decode(_repair_json(raw[start:]))
        except json.JSONDecodeError:
            # Уривок біля помилки — щоб бачити, що саме ламає модель (у промптах лише
            # знеособлені дані, імен учнів тут немає).
            snippet = raw[max(0, start + first.pos - 80) : start + first.pos + 40]
            logger.warning("LLM JSON error at %d near: %r", first.pos, snippet)
            raise first from None
    if not isinstance(data, dict):
        raise ValueError("JSON is not an object")
    return data


def complete_json(
    system: str,
    user: str,
    *,
    kind: str = "fast",
    temperature: float = 0.0,
    max_tokens: int = 600,
    mock: Optional[Dict[str, Any]] = None,
    finalize: Optional[Callable[[Dict[str, Any]], None]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """JSON від LLM. finalize перевіряє й нормалізує дані (кидає ValueError)."""
    if settings.MOCK_LLM:
        data = dict(mock or {})
        if finalize:
            finalize(data)
        return data

    sys = system + "\nВідповідай лише одним JSON-об'єктом, без пояснень і без markdown."
    last: Optional[Exception] = None
    for _ in range(2):  # одна спроба + один повтор
        raw = complete(
            sys, user, kind=kind, temperature=temperature, max_tokens=max_tokens, timeout=timeout
        )
        try:
            data = _extract_json(raw)
            if finalize:
                finalize(data)
            return data
        except (ValueError, KeyError, TypeError) as e:
            last = e
    raise LLMError(f"invalid JSON from model: {last}")