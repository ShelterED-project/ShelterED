import { generateId } from '@/shared/lib/uuid'
import { db } from './db'
import type { EventPayloads, OutboxEvent, SyncEventType } from './types'

/** Подія для шару синхронізації: черга поповнилась. Dexie-хуки спрацьовують до коміту, тому окрема подія. */
export const OUTBOX_ADDED = 'shelter:outbox-added'

let deviceId: Promise<string> | null = null

/** Id пристрою: створюється один раз і живе в IndexedDB. */
export function getDeviceId(): Promise<string> {
  deviceId ??= (async () => {
    const stored = await db.meta.get('device_id')
    if (typeof stored?.value === 'string') return stored.value
    const id = generateId()
    await db.meta.put({ key: 'device_id', value: id })
    return id
  })()
  return deviceId
}

/** Кладе подію в чергу. Час береться з годинника пристрою в момент дії. */
export async function addEvent<T extends SyncEventType>(
  type: T,
  userId: string,
  payload: EventPayloads[T],
): Promise<OutboxEvent> {
  const event = {
    client_event_id: generateId(),
    type,
    device_id: await getDeviceId(),
    occurred_at: new Date().toISOString(),
    payload,
    user_id: userId,
    attempts: 0,
  } as OutboxEvent
  await db.events.add(event)
  window.dispatchEvent(new Event(OUTBOX_ADDED))
  return event
}

/** Найстаріші події користувача за часом події, не більше limit. */
export async function getPendingEvents(userId: string, limit: number): Promise<OutboxEvent[]> {
  const events = await db.events.where('user_id').equals(userId).sortBy('occurred_at')
  return events.slice(0, limit)
}

export async function removeEvents(ids: string[]): Promise<void> {
  await db.events.bulkDelete(ids)
}

export async function markAttempted(ids: string[]): Promise<void> {
  await db.events.where('client_event_id').anyOf(ids).modify((event) => {
    event.attempts += 1
  })
}
