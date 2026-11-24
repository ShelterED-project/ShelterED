import { useLiveQuery } from 'dexie-react-hooks'
import { useOnline } from '@/features/sync/useConnection'
import { db } from '@/shared/db/db'
import type { MediaSource } from './MediaView'

/**
 * Медіа з «Рюкзака» за id: URL файла й субтитрів з таблиці media (маніфест), без мережі.
 * Поки файл не в кеші, пробуємо мережу, якщо вона є.
 */
export function usePackMedia(mediaId: string | null): MediaSource {
  const online = useOnline()
  const found = useLiveQuery(async () => {
    if (!mediaId) return null
    const record = await db.media.get(mediaId)
    if (!record) return null
    const subtitles = record.subtitles_id ? await db.media.get(record.subtitles_id) : undefined
    return { record, subtitles }
  }, [mediaId])

  if (found === undefined) return { src: null, loading: true }
  if (found === null) return { src: null, available: false }
  return {
    src: found.record.url,
    subtitlesSrc: found.subtitles?.url ?? null,
    available: Boolean(found.record.cached_at) || online,
  }
}
