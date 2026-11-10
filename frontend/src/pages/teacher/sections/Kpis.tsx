import iconShelter from '@/assets/admin/kpi-shelter.svg'
import iconClock from '@/assets/parent/kpi-clock.svg'
import iconSafe from '@/assets/teacher/kpi-safe.svg'
import iconQueue from '@/assets/teacher/kpi-queue.svg'
import { useTeacherRollCall } from '@/features/teacher/useTeacherRollCall'
import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { kpiHints, kpis } from '../content'
import type { KpiIcon } from '../content'

type KpiId = (typeof kpis)[number]['id']

const icons: Record<KpiIcon, string> = {
  shelter: iconShelter,
  safe: iconSafe,
  clock: iconClock,
  queue: iconQueue,
}

export default function Kpis() {
  const { session } = useTeacherRollCall()
  const queued = useOutboxCount()
  const total = session?.students.length ?? 0

  const value = (id: KpiId): string => {
    if (id === 'queue') return String(queued)
    return session ? String(session.summary[id]) : '—'
  }
  const hint = (id: KpiId): string => {
    if (id === 'queue') return kpiHints.queue
    return session ? kpiHints.ofStudents(total) : kpiHints.noRollCall
  }

  return (
    <ul className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4">
      {kpis.map((kpi) => (
        <li key={kpi.id}className="flex flex-col gap-2 rounded-[18px] border border-line bg-surface p-4 xl:p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm leading-5 text-dim">{kpi.label}</p>
            <img src={icons[kpi.icon]} alt="" width={18} height={18} className="shrink-0" />
          </div>
          <p
            className={`font-heading text-[30px] leading-[30px] xl:text-[34px] xl:leading-[34px] ${
              kpi.accent ? 'text-accent' : 'text-parchment'
            }`}
          >
            {value(kpi.id)}
          </p>
          <p className="text-xs leading-4 text-dim">{hint(kpi.id)}</p>
        </li>
      ))}
    </ul>
  )
}
