import { store } from '@/app/store'
import { db } from '@/shared/db/db'
import type { LessonProgressRecord, ServerAttemptResult } from '@/shared/db/types'
import { syncApi } from './syncApi'
import type { AttemptResultChange, ModuleProgressChange, SyncChange } from './syncApi'

/** Скільки сторінок стрічки тягнемо за раз; решту — при наступній синхронізації. */
const MAX_PAGES = 10

/** Курсор стрічки окремий для кожного учня: на одному пристрої може бути кілька. */
const cursorKey = (userId: string) => `changes_cursor:${userId}`

/** До якого уроку належать тест чи модуль: беремо з пакетів «Рюкзака» на пристрої. */
async function lessonIndex(): Promise<Map<string, string>> {
  const index = new Map<string, string>()
  for (const pack of await db.packs.toArray()) {
    for (const lesson of pack.lessons) {
      for (const module of lesson.modules) index.set(module.id, lesson.id)
      for (const test of lesson.tests) index.set(test.id, lesson.id)
    }
  }
  return index
}

/**
 * Яку спробу показувати: ту, що прийшла про ту саму спробу (оновлений стан), або зараховану.
 * Незарахована (повтор, після дедлайну) не витісняє вже зараховану.
 */
function preferred(current: ServerAttemptResult | undefined, next: ServerAttemptResult): boolean {
  if (!current || current.client_event_id === next.client_event_id) return true
  if (next.credit_status === 'credited') return true
  return current.credit_status !== 'credited'
}

async function applyAttempt(change: AttemptResultChange, lessons: Map<string, string>) {
  const server: ServerAttemptResult = {
    client_event_id: change.client_event_id,
    score: change.score,
    credit_status: change.credit_status,
    is_suspicious: change.is_suspicious,
  }
  const record = await db.progress.get(change.test_id)
  if (record) {
    if (preferred(record.server, server)) await db.progress.update(change.test_id, { server })
    return
  }
  // Тест пройдено на іншому пристрої: без уроку з пакета показати його ніде, тож пропускаємо.
  const lessonId = lessons.get(change.test_id)
  if (!lessonId) return
  const created: LessonProgressRecord = {
    id: change.test_id,
    kind: 'test',
    lesson_id: lessonId,
    completed_at: new Date().toISOString(),
    score: null,
    server,
  }
  await db.progress.put(created)
}

async function applyModule(change: ModuleProgressChange, lessons: Map<string, string>) {
  if (change.progress_pct < 100 || (await db.progress.get(change.module_id))) return
  const lessonId = lessons.get(change.module_id)
  if (!lessonId) return
  await db.progress.put({
    id: change.module_id,
    kind: 'module',
    lesson_id: lessonId,
    completed_at: change.completed_at ?? new Date().toISOString(),
    score: null,
  })
}

async function apply(userId: string, changes: SyncChange[], nextCursor: string) {
  const lessons = await lessonIndex()
  // Зміни й курсор — однією транзакцією: обрив посередині не загубить і не задвоїть зміни.
  await db.transaction('rw', db.progress, db.meta, async () => {
    for (const change of changes) {
      if (change.kind === 'attempt_result') await applyAttempt(change, lessons)
      else if (change.kind === 'module_progress') await applyModule(change, lessons)
      // rollcall_status не зберігаємо: екран переклички читає актуальну сесію з сервера.
    }
    await db.meta.put({ key: cursorKey(userId), value: nextCursor })
  })
}

/**
 * Підтягує зі стрічки змін результати, які порахував сервер: оцінки оцінюваних тестів,
 * зарахування спроб, модулі, пройдені на іншому пристрої. Лише для учня. Помилки мережі тихі:
 * курсор не зсувається, тож наступна синхронізація продовжить з того самого місця.
 */
export async function pullChanges(): Promise<void> {
  const session = store.getState().auth.session
  if (!session || session.user.role !== 'student') return
  const userId = session.user.id

  const stored = await db.meta.get(cursorKey(userId))
  let cursor = typeof stored?.value === 'string' ? stored.value : null

  for (let page = 0; page < MAX_PAGES; page++) {
    const result = await store.dispatch(
      syncApi.endpoints.syncChanges.initiate(cursor, { forceRefetch: true, subscribe: false }),
    )
    if (!('data' in result) || !result.data) return
    // Поки ми чекали відповідь, міг увійти інший учень: його дані сюди не пишемо.
    if (store.getState().auth.session?.user.id !== userId) return

    const { changes, next_cursor, has_more } = result.data
    if (changes.length > 0 || next_cursor !== cursor) await apply(userId, changes, next_cursor)
    cursor = next_cursor
    if (!has_more) return
  }
}
