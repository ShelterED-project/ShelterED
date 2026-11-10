import iconSafe from '@/assets/parent/status-safe.svg'
import iconShelter from '@/assets/parent/status-shelter.svg'
import iconBell from '@/assets/teacher/bell.svg'
import iconPending from '@/assets/teacher/status-pending.svg'
import { useTeacherRollCall } from '@/features/teacher/useTeacherRollCall'
import { rollCall } from '../content'
import type { RollCallState } from '../content'

const statusStyle: Record<RollCallState, { icon: string; color: string; size: [number, number] }> = {
  shelter: { icon: iconShelter, color: 'text-accent', size: [16, 16] },
  safe: { icon: iconSafe, color: 'text-safe', size: [16, 16] },
  pending: { icon: iconPending, color: 'text-dim', size: [14.28, 16] },
}

function Status({ state, label }: { state: RollCallState; label: string }) {
  const s = statusStyle[state]
  return (
    <span className={`flex items-center gap-1.5 text-sm font-semibold ${s.color}`}>
      <img src={s.icon} alt="" width={s.size[0]} height={s.size[1]} className="shrink-0" />
      <span className={state === 'pending' ? 'max-w-[7ch] md:max-w-none' : undefined}>{label}</span>
    </span>
  )
}

function initials(name: string, lastName: string | null): string {
  return [name, lastName]
    .filter((part): part is string => Boolean(part))
    .map((part) => part[0].toUpperCase())
    .join('')
}

function timeLabel(iso: string | null): string {
  return iso ? new Date(iso).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) : '—'
}

export default function RollCallCard({ className = '' }: { className?: string }) {
  const { session, isLoading } = useTeacherRollCall()
  const students = session?.students ?? []

  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{rollCall.title}</h2>
        {/* TODO: надсилати нагадування тим, хто не відмітився, коли зʼявиться модуль переклички */}
        <button
          type="button"
          className="flex h-10 shrink-0 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-4 text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <img src={iconBell} alt="" width={16} height={16} />
          {rollCall.remind}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="text-xs text-dim">
              <th scope="col" className="pb-2 font-semibold">Учень</th>
              <th scope="col" className="pb-2 font-semibold md:text-center">Статус</th>
              <th scope="col" className="hidden pb-2 text-right font-semibold md:table-cell">Час</th>
            </tr>
          </thead>
          <tbody>
            {students.map((student) => {
              const { state, label } = rollCall.states[student.status]
              const name = [student.display_name, student.last_name].filter(Boolean).join(' ')
              return (
                <tr key={student.student_id} className="border-t border-line-soft">
                  <td className="py-3 pr-3">
                    <span className="flex items-center gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs leading-4 font-semibold text-parchment">
                        {initials(student.display_name, student.last_name)}
                      </span>
                      <span className="text-[15px] leading-[22.5px] font-medium text-parchment">{name}</span>
                    </span>
                  </td>
                  <td className="py-3 pr-3 md:text-center">
                    <span className="md:inline-flex">
                      <Status state={state} label={label} />
                    </span>
                  </td>
                  <td className="hidden py-3 text-right text-sm text-dim md:table-cell">
                    {timeLabel(student.occurred_at)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {!session && (
        <p role="status" className="text-sm text-muted">
          {isLoading ? rollCall.loading : rollCall.empty}
        </p>
      )}
      <p className="text-xs leading-4 text-dim">{rollCall.note}</p>
    </section>
  )
}
