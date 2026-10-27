from typing import Optional

from app.llm import complete
from app.schemas import ChatRequest, ChatResponse, IntentEnum

STYLES = {
    "concise": "Коротко: 3–4 речення, без зайвих слів.",
    "detailed": "Покроково: розбий пояснення на кроки й не пропускай прості перетворення.",
    "example": "Через приклад: спочатку один конкретний приклад із числами або з життя, потім коротке правило.",
}
LEVELS = {
    1: "Починай з найпростішого, ніби дитина чує тему вперше.",
    2: "Додай один розібраний приклад.",
    3: "Поясни детально, чому це працює, і покажи типову помилку.",
}
MAX_TOKENS = {"concise": 250, "detailed": 500, "example": 400}


def _style(req: ChatRequest) -> str:
    s = (req.style or "").strip().lower()
    if s in STYLES:
        return s
    traits = req.profile.traits if req.profile else None
    return "detailed" if traits and traits.needs_detailed_steps else "concise"


def _level(req: ChatRequest) -> Optional[int]:
    try:
        lvl = int(req.level)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return lvl if lvl in LEVELS else None


def _is_weak(req: ChatRequest) -> bool:
    if not (req.profile and req.profile.mastery and req.topic_id):
        return False
    return any(m.topic_id == req.topic_id and m.mastery < 0.4 for m in req.profile.mastery)


def _context(req: ChatRequest) -> str:
    ctx = f"Учень {req.grade} класу"
    if req.subject:
        ctx += f", предмет «{req.subject}»"
    if req.topic:
        ctx += f", поточна тема «{req.topic}»"
    return ctx


async def run(req: ChatRequest) -> ChatResponse:
    message = (req.message or "").strip()

    # немає ні питання, ні теми: нема що пояснювати
    if not message and not req.topic:
        return ChatResponse(
            reply="Напиши, що тебе цікавить, і я поясню.",
            intent=IntentEnum.explain,
            topic_id=req.topic_id,
        )

    style, level = _style(req), _level(req)
    parts = [
        f"Ти — доброзичливий AI-репетитор ShelterED. {_context(req)}.",
        "Відповідай українською простими словами, зрозумілими для цього віку.",
        STYLES[style],
    ]
    if level:
        parts.append(LEVELS[level])
    if _is_weak(req):
        parts.append("Учень слабо знає цю тему: не припускай знань, які він міг пропустити.")
    parts.append(
        "Відповідай на будь-яке питання учня, навіть якщо воно не стосується поточної теми. "
        "Тема, якщо вона є, це лише контекст, а не обмеження."
    )
    parts.append(
        "Не вигадуй фактів: якщо не впевнений, так і скажи. Допомагай зрозуміти, "
        "а не давай готові відповіді на контрольні. Якщо питання недоречне для дитини "
        "або небезпечне, ввічливо відмовся й запропонуй звернутися до дорослого."
    )

    user = message or f"Поясни тему «{req.topic}»."
    reply = complete(
        "\n".join(parts),
        user,
        kind="explain",
        history=req.history,
        temperature=0.4,
        max_tokens=MAX_TOKENS[style],
        mock=f"[MOCK] Пояснення (стиль: {style}).",
    )
    return ChatResponse(reply=reply, intent=IntentEnum.explain, topic_id=req.topic_id)