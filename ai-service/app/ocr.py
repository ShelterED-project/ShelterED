# app/ocr.py
import base64
from io import BytesIO
from PIL import Image
from openai import AsyncOpenAI
from app.config import settings

client = AsyncOpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.AI_KEY
)

def compress_base64_image(raw_base64: str) -> str:
    """Серверна страховка: зменшує великі фото учня до 800px і знижує якість до 75%."""
    if "," in raw_base64:
        raw_base64 = raw_base64.split(",")[1]
    
    image_bytes = base64.b64decode(raw_base64)
    with Image.open(BytesIO(image_bytes)) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((800, 800))
        
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=75)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

async def call_rukopys_ocr(image_base64: str) -> str:
    """Виклик моделі rukopys-ocr через AsyncOpenAI з попереднім стисненням."""
    safe_base64 = compress_base64_image(image_base64)
    
    response = await client.chat.completions.create(
        model="rukopys-ocr",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Розпізнай весь рукописний текст, числа та формули з цієї фотографії зошита."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{safe_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.0
    )
    
    return response.choices[0].message.content or ""