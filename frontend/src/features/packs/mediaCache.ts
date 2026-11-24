import { db } from '@/shared/db/db'
import type { MediaManifestItem } from '@/shared/db/packTypes'
import type { MediaRecord } from '@/shared/db/types'

/**
 * Медіа «Рюкзака» (відео, зображення, VTT) на пристрої. Файли лежать у Cache Storage під тією
 * самою назвою, що й runtime-кеш Workbox у vite.config.ts: Service Worker віддає їх звідти без
 * мережі (CacheFirst, відео частинами через RangeRequestsPlugin). Тут кеш наповнюється
 * наперед, щойно збережено пакет, — щоб урок із відео відкрився в укритті без інтернету.
 */
export const MEDIA_CACHE = 'lesson-media'

const cacheStorage = typeof caches !== 'undefined' ? caches : undefined

/** Кеш доступний лише в захищеному контексті (HTTPS або localhost). */
export const canCacheMedia = Boolean(cacheStorage)

let running: Promise<void> | null = null

/**
 * Записує медіа з маніфесту в таблицю media і прибирає те, на що вже не посилається жоден
 * збережений пакет (разом із файлами в кеші). cached_at лишається, якщо файл той самий.
 */
export async function saveMediaManifest(items: MediaManifestItem[]): Promise<void> {
  const referenced = new Set((await db.packs.toArray()).flatMap((pack) => pack.media ?? []))
  const listed = new Set(items.map((item) => item.id))
  const known = new Map((await db.media.toArray()).map((record) => [record.id, record]))

  const rows: MediaRecord[] = items.map((item) => {
    const old = known.get(item.id)
    const same = old && old.url === item.url && old.sha256 === item.sha256
    return { ...item, cached_at: same ? old.cached_at : null }
  })
  const stale = [...known.values()].filter((record) => !listed.has(record.id) && !referenced.has(record.id))

  await db.transaction('rw', db.media, async () => {
    await db.media.bulkPut(rows)
    await db.media.bulkDelete(stale.map((record) => record.id))
  })

  if (cacheStorage && stale.length > 0) {
    const cache = await cacheStorage.open(MEDIA_CACHE)
    await Promise.all(stale.map((record) => cache.delete(record.url)))
  }
}

async function download() {
  if (!cacheStorage) return
  const cache = await cacheStorage.open(MEDIA_CACHE)
  // Спершу файли на сьогодні, потім на завтра; субтитри маленькі — разом з відео.
  const records = (await db.media.toArray()).sort((a, b) => a.needed_on.localeCompare(b.needed_on))

  for (const record of records) {
    // Браузер міг почистити кеш (без «Захисту даних»): перевіряємо, що файл справді є.
    if (await cache.match(record.url)) {
      if (!record.cached_at) await db.media.update(record.id, { cached_at: new Date().toISOString() })
      continue
    }
    if (record.cached_at) await db.media.update(record.id, { cached_at: null })
    if (!navigator.onLine) return

    // Повний файл без Range (200): з нього SW потім віддає частини відео.
    const response = await fetch(record.url, { cache: 'no-store' }).catch(() => null)
    // Обрив мережі: решту докачаємо при наступній синхронізації.
    if (!response) return
    if (response.status !== 200) continue
    try {
      await cache.put(record.url, response)
    } catch {
      // Немає місця або обірвалось посеред файла: спробуємо пізніше.
      return
    }
    await db.media.update(record.id, { cached_at: new Date().toISOString() })
  }
}

/** Докачує в кеш медіа сьогоднішніх і завтрашніх уроків. Паралельні виклики ділять один запуск. */
export function requestMediaSync(): Promise<void> {
  running ??= download()
    .catch(() => undefined)
    .finally(() => {
      running = null
    })
  return running
}
