# AI-сервіс: як підключити до backend

AI-сервіс — окремий FastAPI на ПК AI-розробника. Backend звертається до нього одним HTTP-запитом.
Повна схема: [`contracts/openapi.yaml`](../contracts/openapi.yaml), або Swagger: `<AI_SERVICE_URL>/docs`.

## 1. Налаштування

`.env` backend:

```dotenv
AI_SERVICE_URL=https://xxxx.trycloudflare.com   # дає AI-розробник; може змінюватися
AI_INTERNAL_KEY=<секрет від AI-розробника>
```

`app/core/config.py`:

```python
    ai_service_url: str = "http://localhost:8000"
    ai_internal_key: SecretStr = SecretStr("")
```

## 2. Код

```python
# app/services/ai.py
import logging

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


async def ask_ai(payload: dict, timeout: float = 30) -> dict:
    """POST /ai/v1/chat. Будь-яка проблема з AI → 503 AI_UNAVAILABLE."""
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{s.ai_service_url}/ai/v1/chat",
                json=payload,
                headers={"X-Internal-Key": s.ai_internal_key.get_secret_value()},
            )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("AI error %s: %s", e.response.status_code, e.response.text[:200])
    except httpx.HTTPError as e:
        logger.warning("AI unreachable: %s", e)  # ПК вимкнений, тунель упав, таймаут
    raise AppError("AI_UNAVAILABLE", "AI tutor is temporarily unavailable", status_code=503)
```

Для перевірки фото (`image_base64`) передавайте `timeout=45`: спершу OCR, потім LLM.

## 3. Приклад: `POST /tutor/ask` (пояснити іншими словами)

Backend сам бере з БД клас, предмет, назву модуля, текст картки і формує запит.
Тут кнопка однозначна, тому `action` передаємо; у вільному чаті його можна не вказувати.

```python
data = await ask_ai({
    "action": "explain",                 # необов'язково: без нього вирішить роутер
    "grade": lesson.grade,
    "subject": subject.code,             # "math"
    "topic": module.title,
    "topic_id": str(module.id),
    "message": f"Поясни цей матеріал іншими словами, з одним прикладом:\n{card_text[:3000]}",
})
return TutorAnswerOut(
    request_id=body.request_id,
    explanation=data["reply"],
    explanation_id=uuid.uuid4(),
    cached=False,
)
```

## 4. Запит

| Поле | Обов'язкове | Що це |
| --- | --- | --- |
| `action` | ні | `explain` \| `practice` \| `check`. **Не передали — режим визначає ML-роутер** за `message` і `history`. Передавайте, лише коли режим уже відомий (кнопка «Підказка», «Перевірити»): так швидше й без помилок класифікації |
| `grade` | так | клас 1–11 |
| `subject`, `topic`, `topic_id` | ні | предмет, назва теми, id теми (повертається без змін) |
| `message` | ні | питання або відповідь учня (для `check`) |
| `image_base64` | ні | фото зошита для `check` |
| `task`, `hints_used` | для `check` і підказок | те, що повернула попередня відповідь `practice` |
| `history` | ні | до 8 реплік `{"role": "user" \| "assistant", "text": "..."}` |

Імен, email, школи **не передавати**. Приклади тіл: `contracts/examples/*.json`.

Мінімальний запит у вільному чаті — `{"grade": 5, "message": "дай задачу на дроби", "task": <збережений або null>, "hints_used": <збережений>, "history": [...]}`.

## 5. Відповідь

```json
{
  "reply": "текст для учня",
  "intent": "explain",
  "topic_id": "…",
  "task": null,
  "hints_used": 0,
  "check_result": null,
  "suggestions": ["⛏️ Копати глибше", "✍️ До практики"]
}
```

- `reply` — показати учню.
- **`intent` — що сервіс зробив насправді** (`explain` \| `practice` \| `check` \| `safety`).
  Якщо `action` не передали, тільки з `intent` видно, що вибрав роутер. Кнопки й екран
  вибирайте за `intent`, а не за тим, що надіслали.
- `intent: "safety"` — учень написав щось тривожне. Показати `reply` як є, без кнопок уроку.
- AI нічого не пам'ятає. **Після кожної відповіді** зберігайте `task` і `hints_used` з неї
  (навіть після `explain`: там повернеться той самий `task`) і надсилайте в наступному запиті.
  Роутер може вирішити, що учень відповідає на завдання, — тоді йому потрібен `task`.
- ⚠️ У `task` є правильна відповідь (`answer`). Фронтенду — лише `task["question"]`.
- `reply` у форматі Markdown — показувати через рендер Markdown, інакше учень побачить `**`.

## 6. Помилки

| Код | Причина | Що робити |
| --- | --- | --- |
| з'єднання / таймаут | ПК AI-розробника вимкнений або тунель перезапущено | 503, фронтенд показує запасний текст |
| 401 | невірний `AI_INTERNAL_KEY` | перевірити ключ |
| 422 | запит не за схемою (`code` у тілі каже, що саме) | виправити запит |
| 503 | LLM недоступна | 503, можна повторити пізніше |

Тіло помилки AI: `{"code": "...", "message": "...", "details": ...}`.

## 7. Перевірка

```bash
curl https://xxxx.trycloudflare.com/health
# {"status":"ok"}

curl -X POST https://xxxx.trycloudflare.com/ai/v1/chat \
  -H "X-Internal-Key: <ключ>" -H "Content-Type: application/json" \
  -d @contracts/examples/explain.json
```

Якщо `/health` не відповідає — AI-сервіс зараз вимкнений, напишіть AI-розробнику.
