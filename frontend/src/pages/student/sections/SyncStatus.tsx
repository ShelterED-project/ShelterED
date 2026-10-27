import iconSync from '@/assets/student/sync.svg'
import { pluralUk } from '@/shared/lib/plural'
import { sync } from '../content'

export default function SyncStatus({ pending }: { pending: number }) {
  const title =
    pending === 0
      ? 'Усе синхронізовано'
      : `${pending} ${pluralUk(pending, ['запис чекає', 'записи чекають', 'записів чекають'])} синхронізації`

  return (
    <section className="flex items-center gap-4 rounded-[22px] border border-line bg-surface p-5">
      <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-surface-2">
        <img src={iconSync} alt="" width={20} height={20} />
      </div>
      <div className="min-w-0 flex-1">
        <p role="status" className="text-[15px] leading-[22.5px] font-semibold text-parchment">
          {title}
        </p>
        <p className="text-xs text-dim">{sync.package}</p>
      </div>
    </section>
  )
}
