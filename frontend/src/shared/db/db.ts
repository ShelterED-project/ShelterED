import Dexie, { type EntityTable } from 'dexie'
import type { OutboxEvent } from './types'

export const db = new Dexie('shelter-ed') as Dexie & {
  outbox: EntityTable<OutboxEvent, 'id'>
}

db.version(1).stores({
  outbox: 'id, createdAt',
})
