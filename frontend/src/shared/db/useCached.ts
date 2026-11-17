import { useEffect } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from './db'

export async function readMeta<T>(key: string): Promise<T | null> {
  const record = await db.meta.get(key)
  return (record?.value as T | undefined) ?? null
}

/**
 * Свіжа відповідь сервера, а без неї — остання збережена в IndexedDB (принцип 1: екран працює
 * зі застарілими даними). Кожна свіжа відповідь перезаписує кеш. key = null — нічого не читаємо.
 */
export function useCached<T>(key: string | null, fresh: T | undefined): T | null {
  const cached = useLiveQuery(async () => (key ? readMeta<T>(key) : null), [key])
  useEffect(() => {
    if (key && fresh) void db.meta.put({ key, value: fresh }).catch(() => undefined)
  }, [key, fresh])
  return fresh ?? cached ?? null
}
