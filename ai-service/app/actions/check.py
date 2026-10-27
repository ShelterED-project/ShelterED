# app/actions/check.py
import json
from typing import Any, Dict
from openai import AsyncOpenAI
from app.ocr import call_rukopys_ocr
from app.config import settings
from app.schemas import CheckResult, ChatRequest, ChatResponse, IntentEnum

client = AsyncOpenAI(
    base_url=settings.LLM_BASE_URL,
    api_key=settings.AI_KEY
)

RUBRIC = """Ти — Mamay — мудрий, підтримуючий та справедливий український вчитель.
Проаналізуй розв'язання учня {grade} класу (предмет «{subject}», тема «{topic}»), яке було розпізнане з його зошита.

Твоє завдання:
1. Перевірити правильність усіх обчислень, виразів або логічних висновків у тексті.
2. Якщо є помилка, м'яко вкажи, у якому саме виразі чи кроці учень припустився хиби (НЕ називай одразу готову відповідь, а підштовхни до правильного розв'язку).
3. Якщо все правильно — похвали учня!

Поверни ВАЛІДНИЙ JSON (без маркерів типу ```json) у такому форматі:
{{
  "score": число від 0.0 до 1.0 (1.0 — усе вірно, 0.0 — суттєві помилки), 
  "error_type": "короткий код помилки (наприклад, calculation_error, logic_error) або null",
  "comment": "1–2 розгорнутих, доброзичливих речення українською від Mamay: що зроблено добре і де варто перевірити себе."
}}"""

def _finalize(data: Dict[str, Any]) -> None:
    score = float(data.get("score", 0.0))  
    data["score"] = max(0.0, min(1.0, score))
    data.setdefault("error_type", None)
    data["comment"] = str(data.get("comment") or "").strip() or "Mamay перевірив роботу. Продовжуй у тому ж дусі!"

async def run(req: ChatRequest) -> ChatResponse:
    # 1. Розпізнаємо текст із фотографії зошита через Rukopys OCR
    student_answer = ""
    if hasattr(req, "image_base64") and req.image_base64:
        student_answer = await call_rukopys_ocr(req.image_base64)
    elif req.message:
        student_answer = req.message

    if not student_answer.strip():
        return ChatResponse(
            reply="Не вдалося розпізнати текст на фото. Спробуй зробити чіткіший знімок зошита!",
            intent=IntentEnum.check,
            check_result=CheckResult(correct=False, score=0.0, error_type="no_answer", method="llm")
        )

    # 2. Формуємо системний та користувацький промпт без використання еталону (answer)
    system_prompt = RUBRIC.format(
        grade=req.grade or "не вказано", 
        subject=req.subject or "Загальний предмет", 
        topic=req.topic or "Обчислення та завдання з зошита"
    )

    user_prompt = (
        f"Розпізнаний рукописний текст із зошита учня:\n"
        f"\"\"\"\n{student_answer}\n\"\"\"\n\n"
        f"Проаналізуй цей текст та оціни правильність виконуваних завдань."
    )

    # 3. Викликаємо MamayLM для автономного аналізу
    response = await client.chat.completions.create(
        model="MamayLM-Gemma-3-27B-IT-v2.0",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0,
        max_tokens=300
    )
    
    raw_content = response.choices[0].message.content or "{}"
    
    try:
        cleaned = raw_content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        data = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        data = {
            "score": 0.5,
            "error_type": "parsing_error",
            "comment": "Mamay перевірив твою роботу! Продовжуй навчатися та вдосконалювати свої знання."
        }

    _finalize(data)
    score = data["score"]
    
    return ChatResponse(
        reply=data["comment"],
        intent=IntentEnum.check,
        topic_id=getattr(req, "topic_id", None),
        task=req.task,
        hints_used=req.hints_used,
        check_result=CheckResult(
            correct=score >= 0.7,
            score=score,
            error_type=data.get("error_type"),
            method="llm",
        ),
    )