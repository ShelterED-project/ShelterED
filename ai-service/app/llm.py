import json
import re
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from app.config import settings


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
) -> str:
    if settings.MOCK_LLM:
        return mock

    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    for m in (history or [])[-8:]:
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
        )
        text = r.choices[0].message.content or ""
    except Exception as e:  # мережа, таймаут, 5xx
        raise LLMError(str(e)) from e

    text = _THINK.sub("", text).strip()   # deepseek-r1 повертає <think>...</think>
    if not text:
        raise LLMError("empty response")
    return text


def _extract_json(raw: str) -> Dict[str, Any]:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object")
    data = json.loads(raw[start : end + 1])
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
        raw = complete(sys, user, kind=kind, temperature=temperature, max_tokens=max_tokens)
        try:
            data = _extract_json(raw)
            if finalize:
                finalize(data)
            return data
        except (ValueError, KeyError, TypeError) as e:
            last = e
    raise LLMError(f"invalid JSON from model: {last}")