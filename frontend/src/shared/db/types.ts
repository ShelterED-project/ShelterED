export interface OutboxEvent {
  /** UUID, створює клієнт до відправки */
  id: string
  /** Тип події, наприклад 'roll_call.marked' */
  type: string
  payload: unknown
  /** Час створення, мс (Date.now()) */
  createdAt: number
  /** Скільки разів намагались відправити */
  attempts: number
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
