from app.llm import complete
from app.schemas import ChatRequest, ChatResponse, IntentEnum


def _context(req: ChatRequest) -> str:
  ctx = f"Учень {req.grade} класу"
  if req.subject:
    ctx += f", предмет «{req.subject}»"
  if req.topic:
    ctx += f", поточна тема «{req.topic}»"
  return ctx


async def run(req: ChatRequest) -> ChatResponse:
  message = (req.message or "").strip()

  # Немає ні питання, ні теми — нема що пояснювати
  if not message and not req.topic:
    return ChatResponse(
        reply="Напиши, що тебе цікавить, і я поясню.",
        intent=IntentEnum.explain,
        topic_id=req.topic_id,
    )

  # Єдиний затверджений стандарт системного промпту для всіх учнів
  system_prompt = "\n".join([
      f"Ти — доброзичливий AI-репетитор ShelterED. {_context(req)}.",
      (
          "Відповідай українською мовою, зрозумілою для школярів цього віку,"
          " дотримуючись стандартів шкільної програми МОН."
      ),
      (
          "Структура твоєї відповіді має бути такою: 1) Дай чітке академічне"
          " визначення або правило простими словами. 2) Наведи один конкретний"
          " розібраний приклад із числами чи життєвою ситуацією. 3) Заверши"
          " пояснення коротким навідним запитанням до учня, щоб перевірити його"
          " розуміння."
      ),
      (
          "Відповідай на будь-яке запитання учня. Якщо тема вказана, використовуй"
          " її як основний контекст."
      ),
      (
          "Не вигадуй фактів. Допомагай зрозуміти суть, а не давай готові"
          " відповіді на домашні чи контрольні завдання. Якщо питання"
          " небезпечне або недоречне, ввічливо відмовся."
      ),
  ])

  user_prompt = message or f"Поясни тему «{req.topic}»."

  reply = complete(
      system_prompt,
      user_prompt,
      kind="explain",
      history=req.history,
      temperature=0.4,
      max_tokens=400,
      mock="[MOCK] Стандартизоване пояснення.",
  )

  return ChatResponse(
      reply=reply, intent=IntentEnum.explain, topic_id=req.topic_id
  )