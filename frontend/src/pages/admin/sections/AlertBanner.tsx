import { Link } from 'react-router'
import iconLantern from '@/assets/admin/alert-lantern.svg'
import type { Alert } from '@/features/alerts/alertsApi'
import { timeLabel } from '@/shared/lib/date'
import { alertBanner as t, navRoutes } from '../content'

type Props = { alert: Alert | null; marked: number; total: number }

export default function AlertBanner({ alert, marked, total }: Props) {
  return (
    <section
      aria-live="polite"
      className={`flex flex-col gap-4 rounded-[22px] border bg-surface-2 p-5 md:flex-row md:items-center ${
        alert ? 'border-accent/40' : 'border-line'
      }`}
    >
      <div className="relative flex size-12 shrink-0 items-center justify-center rounded-full bg-accent-soft">
        {alert && <span className="absolute inset-0 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />}
        <img src={iconLantern} alt="" width={24} height={24} className="relative" />
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="text-[17px] leading-[25.5px] font-semibold text-parchment">
          {alert ? t.active(timeLabel(alert.started_at), alert.is_drill) : t.calm}
        </h2>
        <p className="text-sm leading-5 text-muted">{alert ? t.marked(marked, total) : t.calmText}</p>
      </div>
      <Link
        to={navRoutes.alarms ?? '/admin'}
        className="flex h-12 shrink-0 items-center justify-center rounded-[10px] border border-line-strong px-5 text-[15px] font-semibold whitespace-nowrap text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        {t.journal}
      </Link>
    </section>
  )
}
