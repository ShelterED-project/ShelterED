import type { BackpackStatus } from '@/features/packs/useBackpackStatus'
import { bytesLabel } from '@/pages/settings/content'
import { backpackStatus as t } from '../content'

/** Текст стану «Рюкзака» на сьогодні; null — пакета ще немає (про це кажуть інші тексти). */
export function backpackLine(status: BackpackStatus): { text: string; done: boolean } | null {
  if (!status.ready || !status.saved) return null
  const { mediaCached: done, mediaTotal: total, hasVideo } = status
  if (done >= total) return { text: t.saved(bytesLabel(status.bytes)), done: true }
  if (status.mediaUnsupported) return { text: t.unsupported, done: false }
  return {
    text: status.online ? t.saving(hasVideo, done, total) : t.waiting(hasVideo, done, total),
    done: false,
  }
}
