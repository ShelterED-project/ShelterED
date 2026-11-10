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
  }
}
