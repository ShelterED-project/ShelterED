import { useLiveQuery } from 'dexie-react-hooks'
import { db } from './db'

export function useOutboxCount(): number {
  return useLiveQuery(() => db.outbox.count(), [], 0)
}
