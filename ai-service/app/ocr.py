# app/ocr.py
import base64
import binascii
from io import BytesIO

from app.config import settings
from app.llm import LLMError
from openai import AsyncOpenAI
from PIL import Image, UnidentifiedImageError

DEFAULT_OCR_MODEL = "rukopys-ocr"

_client: AsyncOpenAI | None = None


class InvalidImageError(ValueError):
    """image_base64 не декодується як зображення (HTTP 422 invalid_image)."""


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.AI_KEY,
            timeout=settings.LLM_TIMEOUT,
            max_retries=0,
        )
    return _client


def compress_base64_image(raw_base64: str) -> str:
    """Серверна страховка: зменшує великі фото учня до 800px і знижує якість до 75%."""
    if "," in raw_base64:
        raw_base64 = raw_base64.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(raw_base64, validate=False)
        with Image.open(BytesIO(image_bytes)) as img:
            if img.mode in ("RGBA", "P", "LA", "L"):
                img = img.convert("RGB")
            img.thumbnail((800, 800))
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=75)
    except (binascii.Error, UnidentifiedImageError, OSError, ValueError) as e:
        raise InvalidImageError(str(e)) from e
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def call_rukopys_ocr(image_base64: str) -> str:
    """Розпізнає рукопис на фото. MOCK_LLM=true — лише перевіряє, що це зображення."""
    safe_base64 = compress_base64_image(image_base64)
    if settings.MOCK_LLM:
        return "[MOCK OCR] 30"

    try:
        response = await _get_client().chat.completions.create(
            model=settings.MODEL_OCR or DEFAULT_OCR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Розпізнай весь рукописний текст, числа та формули з цієї фотографії зошита."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{safe_base64}"}},
                    ],
                }
            ],
            temperature=0.0,
        )
    except Exception as e:  # мережа, таймаут, 5xx
        raise LLMError(f"OCR request failed: {e}") from e

    return response.choices[0].message.content or ""
