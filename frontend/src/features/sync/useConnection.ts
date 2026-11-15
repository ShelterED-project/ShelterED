import { useEffect, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '@/shared/db/db'
import { contactKey } from './contact'
import type { ContactChannel } from './contact'

export type ServerState = 'ok' | 'unreachable' | 'unknown'

export interface ConnectionState {
  /** Браузер бачить мережу (navigator.onLine; «є» ще не гарантує, що сервер доступний) */
  online: boolean
  /** Чи відповів сервер на останнє звернення (події або пакети) */
  server: ServerState
  /** Коли сервер востаннє успішно відповів, ISO; null — ще ні разу на цьому пристрої */
  lastOkAt: string | null
  /** Дні, на які уроки збережені на пристрої (YYYY-MM-DD, від сьогодні), за зростанням */
  packDays: string[]
  /** Застосунок збережений Service Worker-ом і відкриється без мережі */
  appOffline: boolean
}

const CHANNELS: ContactChannel[] = ['events', 'packs']

function latest(values: (string | null)[]): string | null {
  return values.reduce<string | null>((max, v) => (v && (!max || v > max) ? v : max), null)
}

/** Сьогоднішня дата пристрою у форматі пакета. */
function todayKey(): string {
  return new Date().toLocaleDateString('sv-SE')
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])
  return online
}

function useAppOffline(): boolean {
  const [ready, setReady] = useState(() => Boolean(navigator.serviceWorker?.controller))
  useEffect(() => {
    const sw = navigator.serviceWorker
    if (!sw) return
    // SW бере сторінку під контроль після першої інсталяції.
    const update = () => setReady(Boolean(sw.controller))
    sw.addEventListener('controllerchange', update)
    return () => sw.removeEventListener('controllerchange', update)
  }, [])
  return ready
}

/**
 * Стан звʼязку для екрана укриття. Усе з локальних даних (IndexedDB, стан браузера), без запитів:
 * сторінка має працювати без мережі й не будити радіомодуль (енергоменеджер).
 */
export function useConnection(): ConnectionState {
  const online = useOnline()
  const appOffline = useAppOffline()

  const contact = useLiveQuery(async () => {
    const keys = CHANNELS.flatMap((c) => [contactKey(c, true), contactKey(c, false)])
    const records = await db.meta.bulkGet(keys)
    const value = (key: string) => {
      const record = records[keys.indexOf(key)]
      return typeof record?.value === 'string' ? record.value : null
    }
    return {
      ok: latest(CHANNELS.map((c) => value(contactKey(c, true)))),
      error: latest(CHANNELS.map((c) => value(contactKey(c, false)))),
    }
  }, [])

  const packDays = useLiveQuery(
    async () => (await db.packs.where('pack_date').aboveOrEqual(todayKey()).toArray()).map((p) => p.pack_date).sort(),
    [],
  )

  const lastOkAt = contact?.ok ?? null
  const lastErrorAt = contact?.error ?? null
  const server: ServerState =
    !lastOkAt && !lastErrorAt ? 'unknown' : lastErrorAt && (!lastOkAt || lastErrorAt > lastOkAt) ? 'unreachable' : 'ok'

  return { online, server, lastOkAt, packDays: packDays ?? [], appOffline }
}
