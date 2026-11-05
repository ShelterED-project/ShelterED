import iconBook from '@/assets/parent/kpi-book.svg'
import iconChart from '@/assets/parent/kpi-chart.svg'
import iconClock from '@/assets/parent/kpi-clock.svg'
import iconMap from '@/assets/parent/kpi-map.svg'
import { kpis } from '../content'
import type { KpiIcon } from '../content'

const icons: Record<KpiIcon, string> = {
  book: iconBook,
  clock: iconClock,
  chart: iconChart,
  map: iconMap,
}

export default function Kpis() {
  return (
    <ul className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      {kpis.map((kpi) => (
        <li key={kpi.label} className="flex flex-col gap-2 rounded-[18px] border border-line bg-surface p-4 md:p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm leading-5 text-dim">{kpi.label}</p>
            <img src={icons[kpi.icon]} alt="" width={18} height={18} className="shrink-0" />
          </div>
          <p
            className={`font-heading text-2xl leading-6 tracking-[-0.24px] md:text-[28px] md:leading-7 md:tracking-[-0.28px] ${
              kpi.accent ? 'text-accent' : 'text-parchment'
            }`}
          >
            {kpi.value}
          </p>
          <p className="text-xs text-dim">{kpi.hint}</p>
        </li>
      ))}
    </ul>
  )
}
