import { db } from '@/shared/db/db'

/**
 * Відповідь учня на картку уроку. На сервер не йде (docs/sync-protocol.md, розділ 10):
 * туди потрапляють лише module_progress і test_attempt. Зберігаємо локально, щоб не втратити.
 */
export function submitAnswer(cardId: string, answer: string) {
  return db.cardAnswers.put({ cardId, answer, answeredAt: Date.now() })
}
