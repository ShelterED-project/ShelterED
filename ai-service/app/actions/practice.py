import uuid
from typing import Any, Dict, Optional

from app.llm import complete, complete_json
from app.schemas import ChatRequest, ChatResponse, IntentEnum

ALLOWED_TYPES = {"choice", "number", "fraction", "text"}

HINT_STEPS = [
    "навідне запитання, яке підштовхує подумати, без підказки відповіді",
    "підказку: яке правило або крок застосувати, без остаточної відповіді",
    "розбір першого кроку розв'язання на цьому завданні, без остаточної відповіді",
]

GEN_SYSTEM = """Ти створюєш одне навчальне завдання для {grade} класу, предмет «{subject}», тема «{topic}».
Складність {difficulty} з 3.
Поверни JSON такого вигляду:
{{"question": "...", "answer_type": "number|fraction|choice|text", "answer": "...",
 "hints": ["навідне запитання", "підказка", "розбір кроку"],
 "common_mistakes": [{{"wrong": "...", "error_type": "...", "feedback": "..."}}]}}
Правила: питання українською, відповідь однозначна. Підказки не називають відповіді."""


def _difficulty(req: ChatRequest) -> int:
    pace = req.profile.traits.pace if req.profile and req.profile.traits else "normal"
    mastery: Optional[float] = None
    if req.profile and req.profile.mastery and req.topic_id:
        for m in req.profile.mastery:
            if m.topic_id == req.topic_id:
                mastery = m.mastery
    if pace == "fast" and (mastery or 0) >= 0.7:
        return 3
    if pace == "slow" or (mastery is not None and mastery < 0.4):
        return 1
    return 2


def _finalize(data: Dict[str, Any]) -> None:
    """Перевіряє лише базову структуру JSON без будь-яких математичних перерахунків."""
    if not str(data.get("question", "")).strip():
        raise ValueError("no question")
    if not str(data.get("answer", "")).strip():
        raise ValueError("no answer")
    
    atype = data.get("answer_type")
    if atype not in ALLOWED_TYPES:
        data["answer_type"] = "text"  # Безпечний дефолт, якщо модель помилилася з типом


def _new_task(req: ChatRequest) -> ChatResponse:
    difficulty = _difficulty(req)
    system = GEN_SYSTEM.format(
        grade=req.grade, subject=req.subject or "загальний", topic=req.topic, difficulty=difficulty
    )
    user = (req.message or "").strip() or "Створи одне завдання."
    
    data = complete_json(
        system,
        user,
        kind="fast",
        temperature=0.5,
        max_tokens=600,
        mock={
            "question": "Скільки буде 2 + 2 * 2?",
            "answer_type": "number",
            "answer": "6",
            "hints": ["Пам'ятай про порядок виконання дій.", "Спочатку множення, потім додавання."],
            "common_mistakes": [
                {"wrong": "8", "error_type": "wrong_order", "feedback": "Ти додав раніше, ніж помножив."}
            ],
        },
        finalize=_finalize,
    )
    
    task = {
        "task_id": f"g-{uuid.uuid4().hex[:6]}",
        "question": str(data["question"]).strip(),
        "answer_type": data["answer_type"],
        "answer": str(data["answer"]).strip(),
        "difficulty": difficulty,
        "hints": [str(h) for h in (data.get("hints") or [])][:3],
        "common_mistakes": (data.get("common_mistakes") or [])[:3],
    }
    
    return ChatResponse(
        reply=f"Завдання: {task['question']}",
        intent=IntentEnum.practice,
        topic_id=req.topic_id,
        task=task,
        hints_used=0,
    )


def _solution(req: ChatRequest, task: Dict[str, Any]) -> ChatResponse:
    answer = task.get("answer", "")
    system = (
        f"Ти — AI-репетитор. Покажи розв'язок крок за кроком для учня {req.grade} класу, "
        "українською, коротко. "
        + (f"Остаточна відповідь: {answer}." if answer else "")
    )
    text = complete(
        system,
        str(task.get("question", "")),
        kind="explain",
        temperature=0.2,
        max_tokens=400,
        mock="[MOCK] Розв'язок крок за кроком.",
    )
    return ChatResponse(
        reply=f"Розв'язок:\n{text}",
        intent=IntentEnum.practice,
        topic_id=req.topic_id,
        task=task,
        hints_used=3,
    )


def _hint(req: ChatRequest, task: Dict[str, Any]) -> ChatResponse:
    n = req.hints_used
    hints = task.get("hints") or []
    if len(hints) > n and str(hints[n]).strip():
        text = str(hints[n]).strip()
    else:
        system = (
            f"Ти — AI-репетитор для учня {req.grade} класу. "
            f"Дай тільки {HINT_STEPS[n]}. Не називай остаточну відповідь. Українською, 1–2 речення."
        )
        text = complete(
            system,
            f"Завдання: {task.get('question', '')}",
            kind="fast",
            temperature=0.3,
            max_tokens=200,
            mock="[MOCK] Підказка.",
        )
    return ChatResponse(
        reply=f"Підказка {n + 1}: {text}",
        intent=IntentEnum.practice,
        topic_id=req.topic_id,
        task=task,
        hints_used=n + 1,
    )


async def run(req: ChatRequest) -> ChatResponse:
    if req.task is None:
        return _new_task(req)
    if req.hints_used >= 3:
        return _solution(req, req.task)
    return _hint(req, req.task)