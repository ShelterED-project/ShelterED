# app/actions/check.py
import asyncio
from functools import partial
from typing import Any, Dict

from app.llm import complete_json
from app.ocr import call_rukopys_ocr
from app.schemas import CheckResult, ChatRequest, ChatResponse, IntentEnum

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

def _expected(task: Dict[str, Any] | None) -> str:
    task = task or {}
    return str(task.get("answer") or task.get("expected_answer") or "").strip()


def _mock_result(req: ChatRequest, student_answer: str) -> Dict[str, Any]:
    """MOCK_LLM: детерміновано порівнює відповідь з еталоном (для тестів і заглушок)."""
    expected = _expected(req.task)
    norm = lambda v: v.lower().replace(" ", "").replace(",", ".")
    ok = bool(expected) and norm(expected) in norm(student_answer)
    return {
        "score": 1.0 if ok else 0.0,
        "error_type": None if ok else "wrong_answer",
        "comment": "[MOCK] Правильно!" if ok else "[MOCK] Є помилка, перевір обчислення.",
    }


def _finalize(data: Dict[str, Any]) -> None:
    score = float(data.get("score", 0.0))
    data["score"] = max(0.0, min(1.0, score))
    data.setdefault("error_type", None)
    data["comment"] = str(data.get("comment") or "").strip() or "Mamay перевірив роботу. Продовжуй у тому ж дусі!"

async def run(req: ChatRequest) -> ChatResponse:
    # 1. Розпізнаємо текст із фотографії зошита через Rukopys OCR
    student_answer = ""
    if req.image_base64:
        student_answer = await call_rukopys_ocr(req.image_base64)
    elif req.message:
        student_answer = req.message

    if not student_answer.strip():
        return ChatResponse(
            reply="Не вдалося розпізнати текст на фото. Спробуй зробити чіткіший знімок зошита!",
            intent=IntentEnum.check,
            topic_id=req.topic_id,
            task=req.task,
            hints_used=req.hints_used,
            check_result=CheckResult(correct=False, score=0.0, error_type="no_answer", method="llm")
        )

    # 2. Формуємо системний та користувацький промпт без використання еталону (answer)
    system_prompt = RUBRIC.format(
        grade=req.grade or "не вказано", 
        subject=req.subject or "Загальний предмет", 
        topic=req.topic or "Обчислення та завдання з зошита"
    )

    question = str((req.task or {}).get("question") or "").strip()
    user_prompt = (
        (f"Умова завдання:\n{question}\n\n" if question else "")
        + f"Розпізнаний рукописний текст із зошита учня:\n"
        f"\"\"\"\n{student_answer}\n\"\"\"\n\n"
        f"Проаналізуй цей текст та оціни правильність виконуваних завдань."
    )

    # 3. Модель — MODEL_EXPLAIN (у .env можна вказати MamayLM-Gemma-3-27B-IT-v2.0).
    #    complete_json: таймаут, один повтор, LLMError → 503, MOCK_LLM.
    data = await asyncio.to_thread(partial(
        complete_json,
        system_prompt,
        user_prompt,
        kind="explain",
        temperature=0.0,
        max_tokens=300,
        mock=_mock_result(req, student_answer),
        finalize=_finalize,
    ))

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