import iconQueue from '@/assets/shelter/queue.svg'
import iconRefresh from '@/assets/shelter/refresh.svg'
import { pluralUk } from '@/shared/lib/plural'
import type { OutboxStats } from '@/shared/db/useOutboxStats'
import { connection } from '../content'

export default function Connection({ stats }: { stats: OutboxStats }) {
  const queue =
    stats.total === 0
      ? 'Черга порожня'
      : `${stats.total} ${pluralUk(stats.total, ['запис', 'записи', 'записів'])} в черзі`

  return (
    <section className="flex flex-col gap-4 rounded-3xl border border-line bg-surface p-5 xl:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment xl:text-[22px] xl:tracking-[-0.22px]">
          {connection.title}
        </h2>
        {/* TODO: статус зʼєднання поки статичний; звʼязати зі станом мережі й локального сервера */}
        <span className="flex items-center gap-1.5 rounded-full bg-line-soft px-3 py-1.5 text-xs font-bold text-accent">
          <span className="size-1.5 rounded-full bg-accent" />
          {connection.status}
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
          <p className="text-xs leading-4 text-dim">{connection.queueHint}</p>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
        {connection.details.map((item) => (
          <div key={item.term}>
            <dt className="text-xs leading-4 text-dim">{item.term}</dt>
            <dd className={`text-sm leading-5 font-semibold ${item.strong ? 'text-parchment' : 'text-muted'}`}>
              {item.value}
            </dd>
          </div>
        ))}
      </dl>

      <dl className="flex flex-col gap-2 border-t border-line-soft pt-4 text-sm leading-5">
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{connection.answers}</dt>
          <dd className="text-dim">{stats.byType['answer.submitted'] ?? 0}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted">{connection.rollCalls}</dt>
          <dd className="text-dim">{stats.byType['roll_call.marked'] ?? 0}</dd>
        </div>
      </dl>

      {/* TODO: запускати відправку черги, коли зʼявиться синхронізація */}
      <button
        type="button"
        className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconRefresh} alt="" width={16} height={16} />
        {connection.retry}
      </button>
    </section>
  )
}
