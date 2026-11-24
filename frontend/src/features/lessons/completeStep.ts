import { db } from '@/shared/db/db'
import { addEvent } from '@/shared/db/outbox'
import type { PackTest } from '@/shared/db/packTypes'
import type { LessonProgressRecord, TestAnswers } from '@/shared/db/types'
import { scoreTest, toWireAnswers } from './grading'

/**
 * Подія й локальний прогрес пишуться в одній транзакції: або є обидва, або жодного.
 * Інакше при збої між записами подія загубилась би (принцип 6) або крок виконувався б двічі.
 * Таблиця meta потрібна addEvent для device_id.
 */
async function recordStep(write: () => Promise<unknown>, record: LessonProgressRecord) {
  await db.transaction('rw', db.events, db.userProgress, db.meta, async () => {
    await write()
    await db.userProgress.put(record)
  })
}

export function completeModule(userId: string, lessonId: string, moduleId: string) {
  const completedAt = new Date().toISOString()
  return recordStep(
    () => addEvent('module_progress', userId, { module_id: moduleId, progress_pct: 100, completed_at: completedAt }),
    { user_id: userId, id: moduleId, kind: 'module', lesson_id: lessonId, completed_at: completedAt, score: null },
  )
}

/**
 * Оцінює сервер після синхронізації; score у подію не передається (протокол v1). Відповіді йдуть
 * у форматі за видом питання: список id, один рядок тексту або пари {лівий: правий}.
 */
export function completeTest(userId: string, lessonId: string, test: PackTest, answers: TestAnswers) {
  const completedAt = new Date().toISOString()
  const wire = toWireAnswers(test, answers)
  return recordStep(
    () => addEvent('test_attempt', userId, { test_id: test.id, answers: wire, completed_at: completedAt }),
    {
      user_id: userId,
      id: test.id,
      kind: 'test',
      lesson_id: lessonId,
      completed_at: completedAt,
      score: scoreTest(test, wire),
    },
  )
}
