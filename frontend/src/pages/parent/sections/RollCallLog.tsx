import iconSafe from '@/assets/parent/status-safe.svg'
import iconShelter from '@/assets/parent/status-shelter.svg'
import { rollCall } from '../content'
import type { RollCallState } from '../content'

function Status({ state, label }: { state: RollCallState; label: string }) {
  if (state === 'none') return <span className="text-sm text-dim">{label}</span>
  const shelter = state === 'shelter'
  return (
    <span className={`flex items-center gap-1.5 text-sm font-semibold ${shelter ? 'text-accent' : 'text-safe'}`}>
      <img src={shelter ? iconShelter : iconSafe} alt="" width={16} height={16} />
      {label}
    </span>
  )
}

export default function RollCallLog({ className = '' }: { className?: string }) {
  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6 ${className}`}>
      <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
        {rollCall.title}
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="text-xs text-dim">
              <th scope="col" className="pb-2 font-semibold">День</th>
              <th scope="col" className="hidden pb-2 font-semibold md:table-cell">Тривога</th>
              <th scope="col" className="pb-2 font-semibold">Статус</th>
              <th scope="col" className="pb-2 text-right font-semibold">Відмітка</th>
            </tr>
          </thead>
          <tbody>
            {rollCall.rows.map((row) => (
              <tr key={row.day} className="border-t border-line-soft">
                <td className="py-3 pr-3 text-[15px] font-medium whitespace-nowrap text-parchment">{row.day}</td>
                <td className="hidden py-3.5 pr-3 text-sm whitespace-nowrap text-dim md:table-cell">{row.alert}</td>
                <td className="py-3 pr-3 whitespace-nowrap">
                  <Status state={row.state} label={row.label} />
                </td>
                <td className="py-3.5 text-right text-sm whitespace-nowrap text-dim">{row.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
