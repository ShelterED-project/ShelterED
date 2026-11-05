import iconSafe from '@/assets/parent/status-safe.svg'
import iconShelter from '@/assets/parent/status-shelter.svg'
import iconBell from '@/assets/teacher/bell.svg'
import iconPending from '@/assets/teacher/status-pending.svg'
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

export default function RollCallCard({ className = '' }: { className?: string }) {
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
            {rollCall.rows.map((row) => (
              <tr key={row.name} className="border-t border-line-soft">
                <td className="py-3 pr-3">
                  <span className="flex items-center gap-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs leading-4 font-semibold text-parchment">
                      {row.initials}
                    </span>
                    <span className="text-[15px] leading-[22.5px] font-medium text-parchment">{row.name}</span>
                  </span>
                </td>
                <td className="py-3 pr-3 md:text-center">
                  <span className="md:inline-flex">
                    <Status state={row.state} label={row.label} />
                  </span>
                </td>
                <td className="hidden py-3 text-right text-sm text-dim md:table-cell">{row.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs leading-4 text-dim">{rollCall.note}</p>
    </section>
  )
}
