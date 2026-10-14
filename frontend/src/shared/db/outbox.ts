import { generateId } from '@/shared/lib/uuid'
import { db } from './db'
import type { OutboxEvent } from './types'

export async function addEvent(type: string, payload: unknown): Promise<OutboxEvent> {
  const event: OutboxEvent = {
    id: generateId(),
    type,
    payload,
    createdAt: Date.now(),
    attempts: 0,
  }
  await db.outbox.add(event)
  return event
}

export function getPendingEvents(): Promise<OutboxEvent[]> {
  return db.outbox.orderBy('createdAt').toArray()
}

export async function removeEvents(ids: string[]): Promise<void> {
  await db.outbox.bulkDelete(ids)
}
