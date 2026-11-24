# Контракт backend <-> AI-сервіс і `POST /tutor/ask`

> Статус: 24.11.2026, реалізовано в backend (B13). Тривоги не входять у цей контракт: API повітряних тривог опитує й розбирає сам backend (B7).

## 1. Контракт AI-сервісу (джерело правди — гілка Романа)

Авторитетний опис — у гілці `feature/ai-service`:

- `contracts/openapi.yaml` — схема `POST /ai/v1/chat` (і `GET /health`);
- `contracts/examples/*.json` — приклади тіл;
- `docs/backend-quickstart.md` — коротка інструкція для backend.

Коротко: `POST {AI_SERVICE_URL}/ai/v1/chat`, заголовок `X-Internal-Key: <AI_INTERNAL_KEY>` (і `X-Request-ID` для наскрізних логів).
Запит: `{action?, grade, subject?, topic?, topic_id?, message?, image_base64?, task?, hints_used?, history? (≤ 8)}`.
Відповідь: `{reply (Markdown), intent (explain|practice|check|safety), topic_id, task, hints_used, check_result?, suggestions}`.
Сервіс stateless: `task`, `hints_used`, `history` зберігає backend. **У `task` є правильна відповідь (`answer`)** — фронтенду вона не віддається ніколи.

Що backend надсилає: `grade` — клас учня (номер), `subject` — назва предмета, `topic`/`topic_id` — назва й id модуля (або уроку), текст картки чи модуля (≤ 3000 символів), репліки учня. Імен, email, школи, id користувача **не надсилаємо** (поле `user_id` контракту не використовуємо).

Налаштування backend (`backend/.env`, див. `backend/README.md`):

| Змінна | За замовчуванням | Що |
| --- | --- | --- |
| `AI_SERVICE_URL` | порожньо | адреса AI-сервісу без `/` у кінці; порожньо — репетитор вимкнений (503) |
| `AI_INTERNAL_KEY` | порожньо | спільний секрет; не логується |
| `AI_TIMEOUT_S` | 30 | таймаут виклику |
| `AI_IMAGE_TIMEOUT_S` | 45 | таймаут виклику з фото (OCR + LLM) |
| `TUTOR_MAX_IMAGE_BYTES` | 4 194 304 | фото в `POST /tutor/ask` після декодування |
| `TUTOR_EXPLANATIONS_INTERVAL_S` | 3600 | beat добирає уроки без закешованих пояснень |
| `RETENTION_TUTOR_CONVERSATION_DAYS` | 30 | розмови без активності видаляються |

Помилки AI → помилки backend (`app/services/ai.py`):

| AI | Backend учню |
| --- | --- |
| з'єднання не вдалося (один повтор), таймаут, 5xx, 404 тунелю, непридатна відповідь, адреса не задана | `503 AI_UNAVAILABLE` |
| `401` (невірний ключ) | `503 AI_UNAVAILABLE` + `ERROR` у лозі «check AI_INTERNAL_KEY» |
| `422 invalid_image` | `422 INVALID_IMAGE` |
| інший `422` (запит не за схемою — помилка backend) | `502 AI_BAD_REQUEST` |

У лог — лише статус і машинний `code` помилки AI, без тексту запиту й відповіді, без ключа.

## 2. `POST /tutor/ask` (backend → фронтенд)

Лише роль `student`, ліміт `RATE_LIMIT_TUTOR` за `RATE_LIMIT_TUTOR_WINDOW_S` (429 з `Retry-After`). Схеми — `TutorAskRequest` / `TutorAnswerOut` у `docs/openapi.json`.

Запит:

```json
{
  "request_id": "uuid — новий на кожне надсилання; повтор того самого = та сама відповідь",
  "conversation_id": "uuid — створює клієнт, один на чат модуля",
  "action": "explain | practice | check (необов'язково: без нього режим вибирає AI)",
  "lesson_id": "uuid?", "module_id": "uuid?", "card_id": "uuid?",
  "message": "текст учня, ≤ 2000 символів?",
  "image_base64": "фото зошита для check: JPEG/PNG, base64 або data URL?"
}
```

- Контекст: досить найвужчого з `lesson_id` / `module_id` / `card_id`; без жодного — береться збережений у розмові. Урок має бути в розкладі чи пакеті класу учня (як для синхронізації), інакше `403`; неіснуючий — `404`; картка не з цього модуля — `422`.
- `explain` + `card_id` — AI пояснює текст картки іншими словами (до 3000 символів); `explain` + модуль без `message` — текстові картки модуля.
- `check` без поточного завдання в розмові — `422 TUTOR_TASK_REQUIRED`; `practice` без завдання й без контексту — `422 TUTOR_TOPIC_REQUIRED`.
- Фото: лише для `check` (або без `action`, тоді це `check`); не JPEG/PNG, не base64, більше за ліміт — `422 INVALID_IMAGE`. Тіло `POST /tutor/ask` має власний ліміт розміру (≈ 4/3 фото + 64 КБ), решта API — `MAX_REQUEST_BODY_BYTES`.
- `history` клієнт не надсилає: її зберігає сервер.

Відповідь:

```json
{
  "request_id": "…", "conversation_id": "…",
  "reply": "Markdown",
  "intent": "explain | practice | check | safety",
  "task": { "question": "…", "answer_type": "number", "options": null },
  "hints_used": 1,
  "suggestions": ["💡 Дай підказку"],
  "check_result": { "correct": false, "score": 0.0 },
  "cached": false
}
```

- `task` — лише умова поточного завдання (білий список `question`, `answer_type`, `options`); `answer`, `expected_answer`, `hints`, `common_mistakes` і будь-які інші поля AI учню не віддаються.
- `intent: safety` — показати `reply` як є, без кнопок уроку; `task: null`, `suggestions: []`.
- `check_result` — лише для `intent: check`.
- `cached: true` — AI недоступний, а учень просив `explain` модуля, для якого є закешоване пояснення (те саме, що в пакеті).
- Невідомий `intent` від AI показується як `explain`.

### Стан розмови (`tutor_conversation`)

- `id` = `conversation_id` клієнта, власник — учень; чужий id — `404` (і для повтору).
- Після кожної відповіді зберігаються `task` (з відповіддю, лише на сервері) і `hints_used` з відповіді AI та дві репліки в історії (учень і AI, ≤ 4000 символів кожна; лише 8 останніх). Наступний запит надсилає їх AI.
- Інший модуль у тій самій розмові — нова тема: завдання й лічильник підказок скидаються.
- Правильна перевірка (`check_result.correct`) закриває завдання: наступне `practice` дасть нове завдання, а не підказку до розв'язаного.
- `intent: safety`: повідомлення учня ніде не зберігається (ні в історії, ні у відповіді для повторів), завдання й підказки не змінюються.
- Розмова видаляється разом з учнем (`ON DELETE CASCADE`) і через `RETENTION_TUTOR_CONVERSATION_DAYS` (30) без активності (`retention.purge`).

### Ідемпотентність

Відповіді на 10 останніх `request_id` зберігаються в розмові (`tutor_conversation.replies`). Повтор того самого `request_id` (обрив до відповіді) повертає збережену відповідь без виклику AI і без витрати ліміту запитів. Якщо два повтори прийшли одночасно, обидва можуть викликати AI, але записується одна відповідь (рядок розмови блокується на час запису; друга бере вже збережену). Транзакція БД не тримається відкритою під час виклику AI.

## 3. Закешовані пояснення для пакета «Рюкзак» (B13.3)

- Публікація уроку ставить Celery-задачу `tutor.explain_lesson` (черга `default`): для кожного модуля з текстовими картками — `action: explain` з текстом модуля (≤ 3000 символів), відповідь зберігається в `tutor_explanation` (унікально на урок + версія + модуль; пояснення старих версій видаляються). Після появи нових пояснень — `packs.rebuild_for_lesson`.
- AI недоступний → отримані пояснення лишаються, задача повторюється кожні 15 хв до доби (96 повторів). Крім того, beat `tutor.explain_missing` раз на `TUTOR_EXPLANATIONS_INTERVAL_S` ставить задачу для опублікованих уроків, у яких є модуль з текстом без пояснення поточної версії. Без `AI_SERVICE_URL` обидві задачі нічого не роблять.
- Пакет: `explanations: [{id, lesson_id, module_id, text}]` — пояснення уроків пакета в їхніх версіях, у порядку уроків і модулів. Вони входять у хеш, тож поява пояснень дає нову версію пакета й push «рюкзак оновився». Клієнт показує їх офлайн і коли `POST /tutor/ask` відповідає 503.
- Відповіді `intent: safety` чи порожні не зберігаються.

## 4. Відкриті питання

- Розбір помилок у тесті (колишній режим `test_review`) у контракті AI окремо не описаний; поки учень може надіслати текст питання як `message`.
- Псевдонім учня (`user_id` = HMAC) і профіль (`profile.mastery`) для персоналізації — не надсилаємо, доки не погоджено мінімізацію даних.
