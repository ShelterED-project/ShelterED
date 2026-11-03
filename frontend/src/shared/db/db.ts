import Dexie, { type EntityTable } from 'dexie'
import type { OutboxEvent, StoredSession } from './types'

export const db = new Dexie('shelter-ed') as Dexie & {
  outbox: EntityTable<OutboxEvent, 'id'>
  session: EntityTable<StoredSession, 'id'>
}

db.version(1).stores({
  outbox: 'id, createdAt',
})

db.version(2).stores({
  outbox: 'id, createdAt',
  session: 'id',
})
