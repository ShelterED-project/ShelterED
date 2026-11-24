import Dexie, { type EntityTable, type Table } from 'dexie'
import type { Pack } from './packTypes'
import type { CardAnswer, LessonProgressRecord, MediaRecord, MetaRecord, OutboxEvent, StoredSession } from './types'

export const db = new Dexie('shelter-ed') as Dexie & {
  /** Ключ [user_id, id модуля чи тесту] */
  userProgress: Table<LessonProgressRecord, [string, string]>
  packs: EntityTable<Pack, 'id'>
  events: EntityTable<OutboxEvent, 'client_event_id'>
  session: EntityTable<StoredSession, 'id'>
  cardAnswers: EntityTable<CardAnswer, 'cardId'>
  meta: EntityTable<MetaRecord, 'key'>
  media: EntityTable<MediaRecord, 'id'>
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

// Прогрес уроків — окремо для кожного учня: на спільному планшеті в укритті входять по черзі,
// і чужі пройдені модулі не мають позначатися як свої. Dexie не змінює первинний ключ таблиці,
// тож прогрес переїжджає в нову таблицю з ключем [user_id+id]. Старі записи без user_id
// привʼязуємо за подіями з черги; решту не вгадуємо — їх поверне стрічка змін сервера
// (курсор стрічки скинуто, див. syncChanges.ts).
db.version(6)
  .stores({
    userProgress: '[user_id+id], [user_id+lesson_id], user_id',
  })
  .upgrade(async (tx) => {
    const owners = new Map<string, string>()
    for (const event of (await tx.table('events').toArray()) as OutboxEvent[]) {
      if (event.type === 'module_progress') owners.set(event.payload.module_id, event.user_id)
      else if (event.type === 'test_attempt') owners.set(event.payload.test_id, event.user_id)
    }
    const old = (await tx.table('progress').toArray()) as Omit<LessonProgressRecord, 'user_id'>[]
    const owned = old.flatMap((record) => {
      const userId = owners.get(record.id)
      return userId ? [{ ...record, user_id: userId }] : []
    })
    await tx.table('userProgress').bulkPut(owned)
  })

// Стара таблиця без user_id більше не потрібна (дані перенесено у version 6).
db.version(7).stores({
  progress: null,
})

// Медіа «Рюкзака»: URL файлів і субтитрів з маніфесту та позначка, чи файл уже в кеші SW.
db.version(8).stores({
  media: 'id',
})
