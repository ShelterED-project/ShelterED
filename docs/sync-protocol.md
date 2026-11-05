# Протокол синхронізації подій

> Статус: **версія 1, бекенд затвердив; чекає підтвердження Максима (frontend) і Олега**. Зміни формату після підтвердження лише сумісні (нові необов'язкові поля). Імена полів взято з моделей `backend/app/models/sync.py`, `rollcall.py`. Схеми вже є в `docs/openapi.json` (`backend/app/schemas/sync.py`: `SyncEventsRequest`, `SyncEventsResponse`, `SyncChangesOut`); ендпоінти поки заглушки (`501 NOT_IMPLEMENTED`), логіка -- B9.

## 1. Загальні правила

- Кожна дія учня = подія з унікальним `client_event_id`, що лежить в outbox (IndexedDB), доки сервер не підтвердить її.
- Сервер приймає подію один раз; повтор того самого `client_event_id` повертає той самий результат (`duplicate`), нічого не дублює й не ламає.
- Один канал для всіх джерел: прямий запит (`source = online`) і QR через телефон вчителя (`source = qr`) йдуть в `POST /sync/events`.
- Користувач береться з JWT, а не з тіла події. Подія з чужим `user_id` неможлива за побудовою.
- Майбутній клієнт -- ноутбук вчителя (локальний сервер укриття, відкладено): він пересилає події учнів тим самим `POST /sync/events` без зміни конверта й payload, як QR-ретрансляція (`relayed_by` = вчитель, `user_id` кожної події береться з підписаного запису учня). Тому клієнт ніколи не покладається на те, що подію відправив сам автор.

## 2. Конверт події

| Поле | Тип | Опис |
| --- | --- | --- |
| `client_event_id` | UUID | Створює клієнт. Рекомендовано v7; сервер приймає будь-який UUID. Це PK `sync_event`. |
| `type` | string | `module_progress`, `test_attempt`, `rollcall_status`, `survey_answer` (CHECK у БД) |
| `device_id` | UUID | Id пристрою, створює клієнт один раз; окремої таблиці `device` немає |
| `occurred_at` | datetime (ISO 8601 з часовим поясом, бажано `Z`) | Час події за годинником пристрою; без поясу -- `422` |
| `payload` | object | Залежить від `type` (розділ 3), зберігається в `sync_event.payload` (JSONB) |

Конверт перевіряється для всього пакета (невалідний `client_event_id`, `device_id`, час -> `422`). `type` і `payload` перевіряються по кожній події окремо: невідомий тип чи невалідний payload дають цій події `rejected` (`unknown_type` / `invalid_payload`), а не `422` всьому пакету, щоб одна погана подія не блокувала outbox. Payload не допускає зайвих полів.

`received_at` і `clock_skew_ms` ставить сервер. `source` визначається сервером за каналом (для QR ще `relayed_by` = вчитель).

## 3. Payload по типах

### `module_progress`

```json
{ "module_id": "0193...-...", "progress_pct": 100, "completed_at": "2026-11-05T09:41:00Z" }
```

`progress_pct` 0..100. `completed_at` (необовʼязково) -> `module_progress.completed_at_client`.

### `test_attempt`

```json
{
  "test_id": "0193...-...",
  "answers": { "<question_id>": ["a"] },
  "completed_at": "2026-11-05T09:50:12Z"
}
```

`answers`: ключ -- `question_id` (UUID), значення -- id обраних варіантів (`Option.id`). `answers` -> `attempt.answers`; `completed_at` (обовʼязковий) -> `attempt.completed_at_client` (від нього рахується вікно тесту). Оцінювання на сервері, `score` у події не передається (зайве поле -> `invalid_payload`).

### `rollcall_status`

```json
{ "session_id": "0193...-...", "status": "in_shelter" }
```

`status` лише `safe` або `in_shelter` (CHECK). «Немає відповіді» = рядка немає, подією не надсилається. Час статусу береться з `occurred_at` конверта.

### `survey_answer`

```json
{ "survey_id": "0193...-...", "question_id": "q1", "value": 3 }
```

`question_id` -- рядок до 32 символів, `value` -- ціле 0..10 (вибір зі шкали). Вільного тексту немає (мінімум даних). Окремої таблиці для опитування в моделі поки немає: подія зберігається в `sync_event`, обробка і окреме сховище з обмеженим доступом погоджуються в B13.4. Формат `value` і перелік питань узгоджується з психологом і Романом. Діагнозів не ставимо.

## 4. `POST /sync/events`

Запит (Bearer JWT):

```json
{
  "sent_at": "2026-11-05T09:55:00Z",
  "events": [
    {
      "client_event_id": "0193a1b2-...",
      "type": "rollcall_status",
      "device_id": "0193a000-...",
      "occurred_at": "2026-11-05T09:54:10Z",
      "payload": { "session_id": "0193...", "status": "in_shelter" }
    }
  ]
}
```

- Відправляє учень (свої події) або вчитель (QR-події учнів своїх класів, B10); інші ролі -- `403`.
- Пакет від 1 до 100 подій, інакше `422` для всього запиту.
- Той самий `client_event_id` двічі в одному пакеті: друга копія отримує `duplicate`.
- `sent_at` -- поточний час пристрою в момент відправки; сервер рахує `clock_skew_ms = received_at - sent_at` для пакета.
- Події обробляються в порядку `occurred_at`; кожна в окремій транзакції, поганa подія не блокує решту.
- Пакет від учня: лише його події. Пакет від вчителя (QR): події учнів його класів, `relayed_by` = вчитель.

Відповідь `200` (загальний статус 200, якщо пакет валідний; результат по кожній події):

```json
{
  "results": [
    { "client_event_id": "0193a1b2-...", "status": "accepted", "reason": null },
    { "client_event_id": "0193a1b3-...", "status": "duplicate", "reason": null },
    { "client_event_id": "0193a1b4-...", "status": "rejected", "reason": "unknown_test" }
  ],
  "server_time": "2026-11-05T09:55:01Z"
}
```

- `accepted` -- збережено й застосовано (у т.ч. якщо програла в конфлікті, див. розділ 5: подія все одно прийнята й записана).
- `duplicate` -- такий `client_event_id` уже є; клієнт видаляє його з outbox.
- `rejected` -- не прийнято, `reason` з розділу 7. Клієнт видаляє з outbox тільки після `accepted`, `duplicate` або `rejected` (повторювати `rejected` безглуздо); при мережевій помилці лишає й повторює.
- Відхилена подія теж записується (`sync_event.status = rejected`, `reject_reason`), тому повтор дає той самий результат.

## 5. Правила конфліктів

| Тип | Правило | Де в БД |
| --- | --- | --- |
| `rollcall_status` | перемагає найпізніший `occurred_at` | `INSERT ... ON CONFLICT (session_id, student_id) DO UPDATE ... WHERE excluded.occurred_at > rollcall_status.occurred_at` |
| `test_attempt` | зараховується перша завершена спроба; решта зберігаються без зарахування | `attempt.credit_status`: `credited`, `not_credited_late` (поза вікном), `not_credited_repeat` |
| `module_progress` | максимум `progress_pct` | `GREATEST(...)` |

Подія, що програла конфлікт, все одно отримує `accepted` (дані записані в журнал); клієнту різниця видна через `GET /sync/changes`.

## 6. Перевірка часу пристрою

- `clock_skew_ms` рахується на пакет (розділ 4).
- Подія з `occurred_at` у майбутньому відносно `received_at` або з великим зсувом (поріг у конфігу, пропозиція: 5 хв) отримує `is_suspicious = true`. **Позначка, не блокування**: подія приймається.
- Для спроб тесту `attempt.is_suspicious` дублює позначку для вчителя.
- Подія, що прийшла через 3 дні, приймається й зараховується за `occurred_at`.

## 7. Коди відхилення (`reason`) -- пропозиція

| Код | Коли |
| --- | --- |
| `invalid_payload` | payload не проходить схему типу |
| `unknown_type` | `type` не з переліку |
| `unknown_entity` | немає `module_id` / `test_id` / `session_id` |
| `forbidden` | немає доступу до сутності (чужий клас, QR від не-вчителя) |
| `session_closed` | перекличка закрита, а `occurred_at` пізніше `closed_at` |

Помилки запиту (не по події): `401` невалідний токен, `403` роль, `422` пакет понад 100 подій або невалідний конверт, `429` rate limit; поки заглушка -- `501 NOT_IMPLEMENTED`. Формат помилки єдиний: `code`, `message`, `details`.

## 8. `GET /sync/changes?cursor=` (чернетка)

```json
{
  "changes": [
    { "kind": "attempt_result", "client_event_id": "0193...", "test_id": "0193...", "credit_status": "credited", "score": 85.0, "is_suspicious": false },
    { "kind": "module_progress", "module_id": "0193...", "progress_pct": 100, "completed_at": "2026-11-05T09:41:00Z" },
    { "kind": "rollcall_status", "session_id": "0193...", "status": "safe", "occurred_at": "2026-11-05T10:20:00Z" }
  ],
  "next_cursor": "1042",
  "has_more": false
}
```

- Без `cursor` -- з початку. Курсор непрозорий для клієнта, монотонний; повтор з тим самим курсором повертає ті самі зміни.
- Без пропусків: `received_at` для цього не годиться (паралельні транзакції комітяться не за порядком). **Рішення:** у змінах зберігаємо `seq` (bigint із sequence) і id транзакції (`xid8`); сервер віддає лише рядки, чия транзакція вже точно закомічена (`xid < pg_snapshot_xmin(pg_current_snapshot())`), тож курсор не перескакує незакомічені записи. Міграція -- у B9.
- Повертає лише дані поточного учня (інші ролі -- `403`). Параметр `limit` (1..500, за замовчуванням 200).
- `kind`: `attempt_result`, `module_progress` (підсумковий максимум), `rollcall_status` (актуальний статус).

## 9. Що змінити у фронтенді

Зараз у `frontend/src/features/*` і `shared/db/types.ts`:

| Зараз | Контракт |
| --- | --- |
| `OutboxEvent.id` | `client_event_id` (UUID, бажано v7) |
| `type: 'roll_call.marked'` | `rollcall_status` |
| `type: 'answer.submitted'` | залежно від дії: `test_attempt` (відповіді на тест), `module_progress` (прогрес), `survey_answer` (опитування); окремої «відповіді на картку» немає |
| `payload: { status }` зі значенням `shelter` | `{ session_id, status }`, статус `in_shelter` (або `safe`) |
| `createdAt` (мс) | `occurred_at` (ISO 8601 UTC) |
| немає `device_id` | генерувати UUID один раз і зберігати |
| немає `session_id` | брати з `GET /classes/{id}/rollcall/current` |
| `payload: { cardId, answer }` | схеми розділу 3 |
| немає `sent_at` | додавати час пристрою до пакета |
| відправка по одній | пакет до 100 подій |

## 10. Ухвалені рішення

- `seq` для `GET /sync/changes` -- так, див. розділ 8 (міграція в B9).
- Зсув годинника: подія «підозріла», якщо `occurred_at` пізніше `received_at` більш ніж на 5 хв або `|clock_skew_ms|` > 5 хв. Позначка, не блокування.
- `survey_answer`: лише ціле 0..10 без тексту; поки зберігається тільки в `sync_event`, окреме сховище з журналом переглядів -- B13.4. Формулювання питань погоджує психолог.
- Відповіді на картки уроку лишаються локальними; на сервер ідуть лише `module_progress` і `test_attempt`.
- Ключ відповідей у пакеті лише для тренувальних вправ модулів; оцінюваний тест із вікном (B11, P1) оцінює сервер після синхронізації.
- Формат QR (B10) стискає ці самі події; підпис і стиснення -- окремий документ від Олега.
