# AI-аналіз тесту класу: як підключити до backend

Вчитель натискає «Проаналізувати» біля тесту → AI повертає:

- **вчителю** — висновок по класу, рекомендації на наступний урок, слабкі вміння, типові помилки
  з переліком учнів, коротку примітку по кожному учню;
- **учню** — його власний фідбек: що вийшло, що повторити й як;
- **батькам** — фідбек про їхню дитину і як допомогти вдома.

Ендпоінт AI: `POST {AI_SERVICE_URL}/ai/v1/test-analysis`. Повна схема — `contracts/openapi.yaml`,
приклад запиту — `contracts/examples/test_analysis.json`.
Налаштування (`AI_SERVICE_URL`, `AI_INTERNAL_KEY`) ті самі, що в [`backend-quickstart.md`](backend-quickstart.md).

## 1. Потік

```
Вчитель: «Проаналізувати»
   → POST /classes/{class_id}/tests/{test_id}/analysis        (backend, лише вчитель класу)
       1. питання тесту + зараховані спроби учнів класу з БД
       2. id учнів → тимчасові псевдоніми s1, s2, …
       3. POST /ai/v1/test-analysis                            (10–60 с)
       4. псевдоніми → id учнів, зберегти результат
   ← вчитель бачить аналіз
Вчитель: «Надіслати учням і батькам»                            (рекомендовано)
   → учні й батьки бачать свій фідбек
```

Крок «Надіслати» — це human-in-the-loop: AI пише чернетку, вчитель переглядає й публікує.
Дитина не отримає від AI текст, якого не бачив дорослий.

## 2. `ask_ai` з параметром шляху

У `app/services/ai.py` (див. quickstart) додайте параметр `path` — для чату нічого не зміниться:

```python
async def ask_ai(payload: dict, timeout: float = 30, path: str = "/ai/v1/chat") -> dict:
    ...
            r = await client.post(f"{s.ai_service_url}{path}", json=payload, headers=...)
```

## 3. Ендпоінт backend

```python
# app/api/analysis.py
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import Session, SettingsDep, TeacherClass
from app.models.lessons import Lesson, Question, Subject, Test
from app.models.sync import Attempt
from app.services.ai import ask_ai
from app.services.stats import _class_students  # select id учнів класу

router = APIRouter(tags=["analysis"])


@router.post("/classes/{class_id}/tests/{test_id}/analysis")
async def analyze_test(test_id: uuid.UUID, klass: TeacherClass, session: Session, settings: SettingsDep):
    test = await session.get(Test, test_id)
    if test is None:
        raise HTTPException(404)
    lesson = await session.get(Lesson, test.lesson_id)
    subject = await session.get(Subject, lesson.subject_id)
    questions = (
        await session.scalars(select(Question).where(Question.test_id == test_id).order_by(Question.position))
    ).all()

    students = list(await session.scalars(_class_students(klass.id)))
    attempts = (
        await session.execute(
            select(Attempt.student_id, Attempt.answers).where(
                Attempt.test_id == test_id,
                Attempt.student_id.in_(students),
                Attempt.credit_status == "credited",
            )
        )
    ).all()
    if not attempts:
        raise HTTPException(409, "Тест ще ніхто не написав")

    # Псевдоніми: у AI не йдуть ні імена, ні справжні id
    alias = {a.student_id: f"s{i}" for i, a in enumerate(attempts, start=1)}
    real = {v: k for k, v in alias.items()}

    data = await ask_ai(
        {
            "grade": klass.grade,
            "subject": subject.name if subject else None,
            "lesson_title": lesson.title,
            "test_title": test.title,
            "pass_score_pct": settings.stats_pass_score,     # той самий поріг, що в кабінетах
            "questions": [
                {
                    "id": str(q.id),
                    "prompt": q.prompt,
                    "kind": q.kind,
                    "options": q.options,
                    "answer_key": q.answer_key,
                    "points": q.points,
                }
                for q in questions
            ],
            "students": [{"student_id": alias[a.student_id], "answers": a.answers or {}} for a in attempts],
        },
        timeout=90,
        path="/ai/v1/test-analysis",
    )

    # Назад до справжніх id
    for s in data["students"]:
        s["student_id"] = str(real[s["student_id"]])
    for m in data["misconceptions"]:
        m["student_ids"] = [str(real[x]) for x in m["student_ids"]]
    for q in data["questions"]:
        for w in q["wrong_answers"]:
            w["student_ids"] = [str(real[x]) for x in w["student_ids"]]
    data["class_summary"]["needs_support_ids"] = [str(real[x]) for x in data["class_summary"]["needs_support_ids"]]

    # Зберегти: test_analysis(id, class_id, test_id, result jsonb, created_at, published_at NULL)
    # Повторне натискання — новий рядок або перезапис (на ваш вибір).
    return data
```

Імена учнів фронтенд підставляє сам за `student_id` (список класу в нього вже є).

## 4. Хто що бачить

| Поле відповіді | Вчитель | Учень | Батьки |
| --- | --- | --- | --- |
| `class_summary` (`overview`, `recommendations`, середній бал) | ✅ | ❌ | ❌ |
| `skills`, `questions`, `misconceptions` (зі списками учнів) | ✅ | ❌ | ❌ |
| `students[].feedback.teacher` | ✅ | ❌ | ❌ |
| `students[].feedback.student` — лише свій | ✅ (перегляд) | ✅ після «Надіслати» | ❌ |
| `students[].feedback.parent` — лише своєї дитини | ✅ (перегляд) | ❌ | ✅ після «Надіслати» |

- Усі тексти — **Markdown**, показувати через рендер Markdown.
- Тексти для учня й батьків не порівнюють дитину з класом і не містять даних інших учнів.
- Списки `student_ids` (хто зробив яку помилку) — **лише вчителю**.

## 5. Поведінка

- **Тривалість 10–60 с.** Таймаут `ask_ai` — 90 с. На фронтенді — індикатор «AI аналізує результати…».
- **LLM недоступна** — AI однаково відповідає `200` зі статистикою й шаблонними текстами,
  `llm_used: false`. Можна показати вчителю: «AI-висновок тимчасово недоступний, показано статистику».
- **AI-сервіс вимкнений / таймаут** — `ask_ai` кидає `503 AI_UNAVAILABLE`, як і для чату.
- **`422 invalid_test`** — тест у БД суперечливий (ключ не з варіантів тощо). Це помилка даних, повтор не допоможе.
- Оцінки збігаються з `attempt.score`: питання зараховане, лише якщо множина обраних варіантів = ключ.

## 6. Перевірка

```bash
curl -X POST https://<домен>.ngrok-free.dev/ai/v1/test-analysis \
  -H "X-Internal-Key: <ключ>" -H "Content-Type: application/json" \
  -d @contracts/examples/test_analysis.json
```

Відповідь — 24 учні, у `misconceptions` перша помилка «додають знаменники» на 12 учнів (питання 1, 5, 6).
