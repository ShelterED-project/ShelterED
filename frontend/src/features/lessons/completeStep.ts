import { db } from '@/shared/db/db'
import { addEvent } from '@/shared/db/outbox'
import type { PackTest } from '@/shared/db/packTypes'
import type { LessonProgressRecord } from '@/shared/db/types'

/**
 * Подія й локальний прогрес пишуться в одній транзакції: або є обидва, або жодного.
 * Інакше при збої між записами подія загубилась би (принцип 6) або крок виконувався б двічі.
 * Таблиця meta потрібна addEvent для device_id.
 */
async function recordStep(write: () => Promise<unknown>, record: LessonProgressRecord) {
  await db.transaction('rw', db.events, db.progress, db.meta, async () => {
    await write()
    await db.progress.put(record)
  })
}

export function completeModule(userId: string, lessonId: string, moduleId: string) {
  const completedAt = new Date().toISOString()
  return recordStep(
    () => addEvent('module_progress', userId, { module_id: moduleId, progress_pct: 100, completed_at: completedAt }),
    { id: moduleId, kind: 'module', lesson_id: lessonId, completed_at: completedAt, score: null },
  )
}

/** Бали за тренувальний тест: питання зараховане, якщо обрана множина дорівнює ключу. Без ключа null. */
export function scoreTest(test: PackTest, answers: Record<string, string[]>): { points: number; max: number } | null {
  if (test.questions.some((q) => q.answer_key == null)) return null
  let points = 0
  let max = 0
  for (const q of test.questions) {
    max += q.points
    const chosen = new Set(answers[q.id] ?? [])
    const key = new Set(q.answer_key ?? [])
    if (chosen.size === key.size && [...chosen].every((id) => key.has(id))) points += q.points
  }
  return { points, max }
}

/** Оцінює сервер після синхронізації; score у подію не передається (протокол v1). */
export function completeTest(userId: string, lessonId: string, test: PackTest, answers: Record<string, string[]>) {
  const completedAt = new Date().toISOString()
  return recordStep(
    () => addEvent('test_attempt', userId, { test_id: test.id, answers, completed_at: completedAt }),
    { id: test.id, kind: 'test', lesson_id: lessonId, completed_at: completedAt, score: scoreTest(test, answers) },
  )
}
