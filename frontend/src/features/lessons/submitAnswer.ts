import { addEvent } from '@/shared/db/outbox'

/** Відповідь учня на картку уроку: фіксується як подія в outbox, на сервер піде при появі звʼязку. */
export function submitAnswer(cardId: string, answer: string) {
  return addEvent('answer.submitted', { cardId, answer })
}
