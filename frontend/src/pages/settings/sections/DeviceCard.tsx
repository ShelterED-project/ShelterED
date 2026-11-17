import { useState } from 'react'
import { requestPackSync } from '@/features/packs/syncPacks'
import { useDeviceStorage } from '@/features/settings/useDeviceStorage'
import { requestSync } from '@/features/sync/syncOutbox'
import { useConnection } from '@/features/sync/useConnection'
import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { dateTimeLabel } from '@/shared/lib/date'
import Spinner from '@/shared/ui/Spinner'
import { bytesLabel, device as t } from '../content'
import { card, heading, outlineButton } from './styles'

/**
 * Стан пристрою: мережа, черга, сховище. Усе з локальних даних, без запитів (енергоменеджер);
 * мережу будить лише кнопка «Синхронізувати зараз». showPacks — для учня, в якого є «Рюкзак».
 */
export default function DeviceCard({ showPacks = false }: { showPacks?: boolean }) {
  const { online, lastOkAt, packDays, appOffline } = useConnection()
  const pending = useOutboxCount()
  const storage = useDeviceStorage()
  const [busy, setBusy] = useState(false)
  const [denied, setDenied] = useState(false)

  const rows: { term: string; value: string; warn: boolean }[] = [
    { term: t.internet, value: online ? t.online : t.offline, warn: !online },
    { term: t.lastSync, value: lastOkAt ? dateTimeLabel(lastOkAt) : t.never, warn: !lastOkAt },
    { term: t.queue, value: t.queueValue(pending), warn: pending > 0 },
    ...(showPacks
      ? [{ term: t.packs, value: packDays.length > 0 ? t.packsDays(packDays.length) : t.packsNone, warn: packDays.length === 0 }]
      : []),
    { term: t.app, value: appOffline ? t.appReady : t.appNotReady, warn: !appOffline },
    ...(storage.usage !== null
      ? [
          {
            term: t.used,
            value: t.usedValue(bytesLabel(storage.usage), storage.quota ? bytesLabel(storage.quota) : null),
            warn: false,
          },
        ]
      : []),
  ]

  async function sync() {
    setBusy(true)
    try {
      await Promise.allSettled([requestSync(), requestPackSync()])
    } finally {
      setBusy(false)
    }
  }

  async function persist() {
    setDenied(!(await storage.requestPersist()))
  }

  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {rows.map((row) => (
          <div key={row.term}>
            <dt className="text-xs text-dim">{row.term}</dt>
            <dd className={`text-sm font-semibold ${row.warn ? 'text-accent' : 'text-parchment'}`}>{row.value}</dd>
          </div>
        ))}
      </dl>
      <button type="button" onClick={() => void sync()} disabled={busy || !online} aria-busy={busy} className={outlineButton}>
        {busy && <Spinner />}
        {busy ? t.syncing : t.sync}
      </button>

      {storage.canPersist && (
        <div className="flex flex-col gap-3 border-t border-line-soft pt-4">
          <div>
            <p className="text-[15px] font-semibold text-parchment">{t.persist.title}</p>
            <p className={`mt-1 text-sm ${storage.persisted ? 'text-safe' : 'text-muted'}`}>
              {storage.persisted ? t.persist.on : t.persist.off}
            </p>
          </div>
          {!storage.persisted && (
            <button type="button" onClick={() => void persist()} className={outlineButton}>
              {t.persist.button}
            </button>
          )}
          {denied && !storage.persisted && (
            <p role="status" className="text-sm text-dim">
              {t.persist.denied}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
