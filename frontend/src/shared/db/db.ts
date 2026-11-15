import Dexie, { type EntityTable } from 'dexie'
import type { Pack } from './packTypes'
import type { CardAnswer, LessonProgressRecord, MetaRecord, OutboxEvent, StoredSession } from './types'

export const db = new Dexie('shelter-ed') as Dexie & {
  progress: EntityTable<LessonProgressRecord, 'id'>
  packs: EntityTable<Pack, 'id'>
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

// «Рюкзак»: пакети на день для офлайн-уроків. Ключ id, за pack_date чистимо минулі дні.
db.version(4).stores({
  packs: 'id, pack_date, class_id',
})

// Локальний прогрес уроків: завершені модулі й здані тести (джерело для екрана уроку).
db.version(5).stores({
  progress: 'id, lesson_id',
})
