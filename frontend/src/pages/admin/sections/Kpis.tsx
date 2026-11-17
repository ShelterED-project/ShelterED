import iconClasses from '@/assets/register/icon-school.svg'
import iconBell from '@/assets/admin/kpi-bell.svg'
import iconShelter from '@/assets/admin/kpi-shelter.svg'
import iconWifi from '@/assets/admin/kpi-wifi.svg'
import { kpis as t } from '../content'

type Props = {
  shelter: { inShelter: number; safe: number; total: number }
  hasRollCall: boolean
  classes: number
  teachers: number
  alarms: number
  alarmMinutes: number
}

export default function Kpis({ shelter, hasRollCall, classes, teachers, alarms, alarmMinutes }: Props) {
  const items = [
    {
      label: t.shelter.label,
      value: hasRollCall ? String(shelter.inShelter) : '—',
      hint: t.shelter.hint(shelter.total, shelter.safe),
      icon: iconShelter,
      accent: true,
    },
    { label: t.classes.label, value: String(classes), hint: t.classes.hint(teachers), icon: iconClasses },
    { label: t.alarms.label, value: String(alarms), hint: t.alarms.hint(alarmMinutes), icon: iconBell },
    { label: t.servers.label, value: t.servers.value, hint: t.servers.hint, icon: iconWifi },
  ]
  return (
    <ul className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4">
      {items.map((kpi) => (
        <li key={kpi.label} className="flex flex-col gap-2 rounded-[18px] border border-line bg-surface p-4 xl:p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm leading-5 text-dim">{kpi.label}</p>
            <img src={kpi.icon} alt="" width={18} height={18} className="shrink-0" />
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
