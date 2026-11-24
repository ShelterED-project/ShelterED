import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '@/shared/db/db'
import { useOnline } from '@/features/sync/useConnection'
import { canCacheMedia } from './mediaCache'
import { packOn } from './usePacks'

export interface BackpackStatus {
  /** false, поки читаємо з пристрою */
  ready: boolean
  /** Пакет на сьогодні (текст уроків і тести) є на пристрої */
  saved: boolean
  /** Скільки займають сьогоднішні уроки на пристрої: пакет і збережені медіа, байти */
  bytes: number
  /** Відео й малюнки сьогоднішніх карток: усього і вже на пристрої */
  mediaTotal: number
  mediaCached: number
  /** Серед медіа є відео (для тексту «Зберігаю відео…») */
  hasVideo: boolean
  /** Є мережа: медіа докачуються зараз, а не «коли буде інтернет» */
  online: boolean
  /** Браузер не вміє зберігати медіа (не HTTPS): відео лише з інтернетом */
  mediaUnsupported: boolean
}

function todayKey(): string {
  return new Date().toLocaleDateString('sv-SE')
}


const encoder = new TextEncoder()

/**
 * Чи готовий сьогоднішній урок без мережі: пакет і медіа його карток. Усе з IndexedDB,
 * без запитів; оновлюється, щойно syncPacks/mediaCache збережуть новий файл.
 */
export function useBackpackStatus(): BackpackStatus {
  const online = useOnline()
  const data = useLiveQuery(async () => {
    const pack = await packOn(todayKey())
    if (!pack) return null
    const cardMedia = new Set(
      pack.lessons.flatMap((l) => l.modules.flatMap((m) => m.cards.flatMap((c) => (c.media_asset_id ? [c.media_asset_id] : [])))),
    )
    const records = (await db.media.bulkGet([...cardMedia])).filter((r) => r !== undefined)
    const subtitleIds = records.flatMap((r) => (r.subtitles_id ? [r.subtitles_id] : []))
    const subtitles = (await db.media.bulkGet(subtitleIds)).filter((r) => r !== undefined)
    const cached = [...records, ...subtitles].filter((r) => r.cached_at)
    return {
      packBytes: encoder.encode(JSON.stringify(pack)).length,
      mediaBytes: cached.reduce((sum, r) => sum + r.size_bytes, 0),
      total: cardMedia.size,
      cached: records.filter((r) => r.cached_at).length,
      hasVideo: records.some((r) => r.kind === 'video'),
    }
  }, [])

  return {
    ready: data !== undefined,
    saved: Boolean(data),
    bytes: data ? data.packBytes + data.mediaBytes : 0,
    mediaTotal: data?.total ?? 0,
    mediaCached: data?.cached ?? 0,
    hasVideo: data?.hasVideo ?? false,
    online,
    mediaUnsupported: !canCacheMedia,
  }
}
