import { useState } from 'react'
import iconQueue from '@/assets/shelter/queue.svg'
import iconRefresh from '@/assets/shelter/refresh.svg'
import { requestPackSync } from '@/features/packs/syncPacks'
import { requestSync } from '@/features/sync/syncOutbox'
import { useConnection } from '@/features/sync/useConnection'
import type { OutboxStats } from '@/shared/db/useOutboxStats'
import { pluralUk } from '@/shared/lib/plural'
import Spinner from '@/shared/ui/Spinner'
import { connection } from '../content'

/** «сьогодні о 14:05» або «10 лист., 14:05» */
function whenLabel(iso: string): string {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === new Date().toDateString()) return `сьогодні о ${time}`
  return `${date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })}, ${time}`
}

function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })
}

export default function Connection({ stats }: { stats: OutboxStats }) {
  const { online, server, lastOkAt, packDays, appOffline } = useConnection()
  const [busy, setBusy] = useState(false)

  const status = !online ? 'offline' : server === 'unreachable' ? 'unreachable' : 'online'
  const statusStyle = status === 'online' ? 'text-safe' : 'text-accent'
  const dotStyle = status === 'online' ? 'bg-safe' : 'bg-accent'

  const queue =
    stats.total === 0
      ? connection.queueEmpty
      : `${stats.total} ${pluralUk(stats.total, ['запис', 'записи', 'записів'])} в черзі`

  const details: { term: string; value: string; warn: boolean }[] = [
    {
      term: connection.internet.term,
      value: online ? connection.internet.yes : connection.internet.no,
      warn: !online,
    },
    {
      term: connection.server.term,
      value: connection.server[server],
      warn: server === 'unreachable',
    },
    {
      term: connection.lastSync.term,
      value: lastOkAt ? whenLabel(lastOkAt) : connection.lastSync.never,
      warn: !lastOkAt,
    },
    {
      term: connection.packs.term,
      value:
        packDays.length > 0
          ? connection.packs.days(
              packDays.length,
              dayLabel(packDays[packDays.length - 1]),
              pluralUk(packDays.length, ['день', 'дні', 'днів']),
            )
          : connection.packs.none,
      warn: packDays.length === 0,
    },
    {
      term: connection.app.term,
      value: appOffline ? connection.app.ready : connection.app.notReady,
      warn: !appOffline,
    },
  ]

  const retry = async () => {
    setBusy(true)
    try {
      await Promise.allSettled([requestSync(), requestPackSync()])
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-3xl border border-line bg-surface p-5 xl:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment xl:text-[22px] xl:tracking-[-0.22px]">
          {connection.title}
        </h2>
        <span
          role="status"
          className={`flex items-center gap-1.5 rounded-full bg-line-soft px-3 py-1.5 text-xs font-bold ${statusStyle}`}
        >
          <span className={`size-1.5 rounded-full ${dotStyle}`} />
          {connection.status[status]}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2">
          <img src={iconQueue} alt="" width={20} height={20} />
        </div>
        <div>
          <p role="status" className="text-sm leading-5 font-semibold text-parchment">
            {queue}
          </p>
          <p className="text-xs leading-4 text-dim">{stats.total === 0 ? connection.queueSentHint : connection.queueHint}</p>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {details.map((item) => (
          <div key={item.term}>
            <dt className="text-xs leading-4 text-dim">{item.term}</dt>
            <dd className={`text-sm leading-5 font-semibold ${item.warn ? 'text-accent' : 'text-parchment'}`}>
              {item.value}
            </dd>
          </div>
        ))}
      </dl>

      <dl className="flex flex-col gap-2 border-t border-line-soft pt-4 text-sm leading-5">
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{connection.answers}</dt>
          <dd className="text-dim">{(stats.byType['test_attempt'] ?? 0) + (stats.byType['module_progress'] ?? 0)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{connection.rollCalls}</dt>
          <dd className="text-dim">{stats.byType['rollcall_status'] ?? 0}</dd>
        </div>
      </dl>

      <button
        type="button"
        onClick={() => void retry()}
        disabled={busy}
        aria-busy={busy}
        className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60"
      >
        {busy ? <Spinner /> : <img src={iconRefresh} alt="" width={16} height={16} />}
        {busy ? connection.retrying : connection.retry}
      </button>
    </section>
  )
}
