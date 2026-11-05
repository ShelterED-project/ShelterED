import { useLiveQuery } from 'dexie-react-hooks'
import { db } from './db'

export type OutboxStats = { total: number; byType: Record<string, number> }

const empty: OutboxStats = { total: 0, byType: {} }

/** Кількість подій у черзі: усього й за типами (наприклад, 'roll_call.marked'). */
export function useOutboxStats(): OutboxStats {
  return useLiveQuery(
    async () => {
      const events = await db.outbox.toArray()
      const byType: Record<string, number> = {}
      for (const event of events) byType[event.type] = (byType[event.type] ?? 0) + 1
      return { total: events.length, byType }
    },
    [],
    empty,
  )
}
