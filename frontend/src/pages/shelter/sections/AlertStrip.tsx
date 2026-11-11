import { useState } from 'react'
import { Link } from 'react-router'
import iconSound from '@/assets/shelter/sound-off.svg'
import type { Alert } from '@/features/alerts/alertsApi'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import { alert as texts } from '../content'

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}

/** Рядок тривоги: показує активну тривогу, а коли вона зникла зі списку активних, відбій. */
export default function AlertStrip() {
  const { alert } = useActiveAlert()
  // Остання побачена тривога: коли її більше немає серед активних, це відбій.
  const [seen, setSeen] = useState<Alert | null>(null)
  if (alert && seen?.id !== alert.id) setSeen(alert)
  const ended = !alert && seen !== null

  if (!alert && !ended) return null

  if (!alert) {
    return (
      <div role="status" className="border-b border-line bg-surface-2">
        <div className="mx-auto flex h-11 max-w-[1296px] items-center gap-3 px-5 md:px-8 xl:px-10">
          <span className="size-2.5 shrink-0 rounded-full bg-safe" />
          <p className="text-sm leading-5 font-bold whitespace-nowrap text-safe">{texts.endedTitle}</p>
          <p className="min-w-0 truncate text-sm leading-5 text-muted">{texts.endedText}</p>
          <Link
            to="/student"
            className="ml-auto text-sm font-semibold whitespace-nowrap text-parchment underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {texts.home}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div role="alert" className="border-b border-accent/40 bg-accent-soft">
      <div className="mx-auto flex h-11 max-w-[1296px] items-center gap-3 px-5 md:px-8 xl:px-10">
        <span className="size-2.5 shrink-0 rounded-full bg-accent" />
        <p className="text-sm leading-5 font-bold whitespace-nowrap text-accent">
          {alert.is_drill ? texts.drillTitle : texts.title}
        </p>
        <p className="min-w-0 truncate text-sm leading-5 text-muted">{texts.since(timeLabel(alert.started_at))}</p>
        <p className="ml-auto hidden items-center gap-1.5 text-xs text-dim md:flex">
          <img src={iconSound} alt="" width={16} height={16} />
          {texts.sound}
        </p>
      </div>
    </div>
  )
}
