/** Payload подій за типом, див. docs/sync-protocol.md, розділ 3. */
export interface EventPayloads {
  rollcall_status: { session_id: string; status: 'safe' | 'in_shelter' }
  module_progress: { module_id: string; progress_pct: number; completed_at?: string }
  test_attempt: { test_id: string; answers: Record<string, string[]>; completed_at: string }
  survey_answer: { value: 1 | 2 | 3 | 4 | 5 }
}

export type SyncEventType = keyof EventPayloads

interface OutboxEventBase<T extends SyncEventType> {
  /** UUID, створює клієнт до відправки; сервер за ним відсіює дублі */
  client_event_id: string
  type: T
  /** Id пристрою, створюється один раз */
  device_id: string
  /** Час події за годинником пристрою, ISO 8601 UTC */
  occurred_at: string
  payload: EventPayloads[T]
  /** Чий це запис: подію не можна відправити з токеном іншого користувача (локальне поле, на сервер не йде) */
  user_id: string
  /** Скільки разів намагались відправити (локальне поле) */
  attempts: number
}

export type OutboxEvent = { [T in SyncEventType]: OutboxEventBase<T> }[SyncEventType]

/** Подія в тому вигляді, в якому йде в POST /sync/events. */
export type WireEvent = Pick<OutboxEvent, 'client_event_id' | 'type' | 'device_id' | 'occurred_at' | 'payload'>

/** Відповідь учня на картку уроку. Лишається локальною (docs/sync-protocol.md, розділ 10). */
export interface CardAnswer {
  cardId: string
  answer: string
  /** Коли відповів, мс (Date.now()) */
  answeredAt: number
}

/**
 * Локальний прогрес учня: завершений модуль або зданий тест. Екран уроку читає його звідси,
 * бо події з outbox зникають після підтвердження сервером.
 */
export interface LessonProgressRecord {
  /** id модуля або тесту */
  id: string
  kind: 'module' | 'test'
  lesson_id: string
  /** ISO 8601 UTC, час пристрою */
  completed_at: string
  /** Для тесту з ключем: набрані бали й максимум; для оцінюваного тесту без ключа null */
  score: { points: number; max: number } | null
  /**
   * Результат від сервера (GET /sync/changes): оцінка 0..100 і зарахування. Поки сервер
   * не відповів — відсутнє. Поле без індексу, тож нова версія Dexie не потрібна.
   */
  server?: ServerAttemptResult
}

export type CreditStatus = 'credited' | 'not_credited_late' | 'not_credited_repeat'

export interface ServerAttemptResult {
  client_event_id: string
  score: number | null
  credit_status: CreditStatus
  is_suspicious: boolean
}

/** Дрібні значення пристрою: device_id, остання відома сесія переклички. */
export interface MetaRecord {
  key: string
  value: unknown
}

/** Збережений вхід, щоб відкривати застосунок без мережі. Один запис з id 'current'. */
export interface StoredSession {
  id: 'current'
  accessToken: string
  refreshToken: string
  /** Коли спливає access-токен, мс (Date.now()) */
  expiresAt: number
  user: {
    id: string
    role: string
    display_name: string
    last_name: string | null
    school_id: string | null
    class_id?: string | null
  }
}
