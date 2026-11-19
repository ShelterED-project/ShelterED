import { useEffect, useState } from 'react'

export interface DeviceStorage {
  /** Зайнято й доступно, байти; null — браузер не каже */
  usage: number | null
  quota: number | null
  /** Браузер не чиститиме дані сам (уроки, черга) навіть при нестачі місця */
  persisted: boolean
  /** Браузер уміє просити захист даних */
  canPersist: boolean
  /** Попросити захист; повертає, чи браузер погодився */
  requestPersist: () => Promise<boolean>
}

const storage = typeof navigator !== 'undefined' ? navigator.storage : undefined

/**
 * Сховище пристрою: скільки займають уроки й черга і чи захищені вони від автоочищення.
 * Без захисту браузер може стерти IndexedDB при нестачі місця, разом із невідправленими відповідями.
 */
export function useDeviceStorage(): DeviceStorage {
  const [estimate, setEstimate] = useState<{ usage: number | null; quota: number | null }>({ usage: null, quota: null })
  const [persisted, setPersisted] = useState(false)

  useEffect(() => {
    let alive = true
    storage
      ?.estimate?.()
      .then((e) => alive && setEstimate({ usage: e.usage ?? null, quota: e.quota ?? null }))
      .catch(() => undefined)
    storage
      ?.persisted?.()
      .then((value) => alive && setPersisted(value))
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  async function requestPersist(): Promise<boolean> {
    try {
      const granted = (await storage?.persist?.()) ?? false
      setPersisted(granted)
      return granted
    } catch {
      return false
    }
  }

  return { ...estimate, persisted, canPersist: Boolean(storage?.persist), requestPersist }
}
