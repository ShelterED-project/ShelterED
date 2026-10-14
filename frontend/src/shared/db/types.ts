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
