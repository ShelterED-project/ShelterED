import Dexie, { type EntityTable } from 'dexie'
import type { CardAnswer, MetaRecord, OutboxEvent, StoredSession } from './types'

export const db = new Dexie('shelter-ed') as Dexie & {
  events: EntityTable<OutboxEvent, 'client_event_id'>
  session: EntityTable<StoredSession, 'id'>
  cardAnswers: EntityTable<CardAnswer, 'cardId'>
  meta: EntityTable<MetaRecord, 'key'>
}

db.version(1).stores({
  outbox: 'id, createdAt',
})

db.version(2).stores({
  outbox: 'id, createdAt',
  session: 'id',
})

// Протокол синхронізації v1: первинний ключ client_event_id. Dexie не вміє міняти ключ таблиці,
// тому черга переїжджає в нову таблицю events. Старі записи (roll_call.marked без session_id,
// answer.submitted) протокол не приймає, тож стару таблицю outbox прибираємо.
db.version(3).stores({
  outbox: null,
  events: 'client_event_id, occurred_at, user_id',
  session: 'id',
  cardAnswers: 'cardId',
  meta: 'key',
})
