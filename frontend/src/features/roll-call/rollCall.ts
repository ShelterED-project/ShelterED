import { db } from '@/shared/db/db'
import { addEvent } from '@/shared/db/outbox'
import type { RollCallStatus } from './types'

const SESSION_KEY = 'rollcall_session_id'

/** Остання відома сесія переклички: потрібна, щоб відмітитись, коли мережі немає. */
export async function getCachedSessionId(): Promise<string | null> {
  const stored = await db.meta.get(SESSION_KEY)
  return typeof stored?.value === 'string' ? stored.value : null
}

export async function cacheSessionId(sessionId: string | null): Promise<void> {
  if (sessionId) await db.meta.put({ key: SESSION_KEY, value: sessionId })
  else await db.meta.delete(SESSION_KEY)
}

export function markStatus(userId: string, sessionId: string, status: RollCallStatus) {
  return addEvent('rollcall_status', userId, { session_id: sessionId, status })
}
