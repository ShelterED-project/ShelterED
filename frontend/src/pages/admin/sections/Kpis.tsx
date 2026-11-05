import iconClasses from '@/assets/register/icon-school.svg'
import iconBell from '@/assets/admin/kpi-bell.svg'
import iconShelter from '@/assets/admin/kpi-shelter.svg'
import iconWifi from '@/assets/admin/kpi-wifi.svg'
import { kpis } from '../content'
import type { KpiIcon } from '../content'

const icons: Record<KpiIcon, string> = {
  shelter: iconShelter,
  classes: iconClasses,
  bell: iconBell,
  wifi: iconWifi,
}

export default function Kpis() {
  return (
    <ul className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4">
      {kpis.map((kpi) => (
        <li key={kpi.label} className="flex flex-col gap-2 rounded-[18px] border border-line bg-surface p-4 xl:p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm leading-5 text-dim">{kpi.label}</p>
            <img src={icons[kpi.icon]} alt="" width={18} height={18} className="shrink-0" />
          </div>
          <p
            className={`font-heading text-[28px] leading-7 xl:text-[34px] xl:leading-[34px] ${
              kpi.accent ? 'text-accent' : 'text-parchment'
            }`}
          >
            {kpi.value}
          </p>
          <p className="text-xs leading-4 text-dim">{kpi.hint}</p>
        </li>
      ))}
    </ul>
  )
}
