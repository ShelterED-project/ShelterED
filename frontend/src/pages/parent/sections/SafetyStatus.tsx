import iconClock from '@/assets/parent/clock-sm.svg'
import iconShield from '@/assets/parent/shield-check.svg'
import type { Alert } from '@/features/alerts/alertsApi'
import type { StudentRollCall } from '@/features/roll-call/rollCallApi'
import { timeLabel } from '@/shared/lib/date'
import { safetyStatus as t } from '../content'

type Props = {
  name: string
  alert: Alert | null
  rollCall: StudentRollCall | null
  updatedAt: number | null
  isOffline: boolean
}

export default function SafetyStatus({ name, alert, rollCall, updatedAt, isOffline }: Props) {
  const session = rollCall?.session_id ? rollCall : null
  const status = session?.status ?? null
  const marked = session?.occurred_at ?? null

  let title = t.calm
  let text = t.calmText
  if (session) {
    title = status === 'in_shelter' ? t.inShelter(name) : status === 'safe' ? t.safe(name) : t.noMark(name)
    text = marked ? t.markedAt(timeLabel(marked)) : t.noMarkText
  } else if (alert) {
    title = t.noRollCall
    text = t.noMarkText
  }

  const drill = session?.is_drill ?? alert?.is_drill ?? false
  const startedAt = alert?.started_at ?? session?.opened_at ?? null
  const alertLine = startedAt ? t.alert(timeLabel(startedAt), drill) : t.noAlert
  const ok = !session || status !== null

  return (
    <section
      aria-labelledby="safety-title"
      aria-live="polite"
      className={`flex flex-col gap-4 overflow-clip rounded-[22px] border bg-surface-2 p-5 md:flex-row md:items-center md:gap-6 md:p-6 ${
        ok ? 'border-safe/40' : 'border-accent/50'
      }`}
    >
      <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-safe/15">
        <img src={iconShield} alt="" width={28} height={28} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 pt-[5.5px] md:pt-0">
        <p className="text-xs font-bold tracking-[1.5px] text-accent uppercase">{alertLine}</p>
        <h2
          id="safety-title"
          className="pt-[1.5px] font-heading text-[22px] leading-[27.5px] tracking-[-0.22px] text-parchment md:text-[26px] md:leading-[32.5px] md:tracking-[-0.26px]"
        >
          {title}
        </h2>
        <p className="text-sm leading-5 text-muted">{text}</p>
      </div>
      <div className="flex flex-col gap-1 md:items-end md:text-right">
        <p className="flex items-center gap-1.5 text-xs text-dim">
          <img src={iconClock} alt="" width={16} height={16} />
          {isOffline || !updatedAt ? t.dataOffline : t.dataTime(timeLabel(updatedAt))}
        </p>
        <p className="max-w-[260px] text-xs text-dim">{t.note}</p>
      </div>
    </section>
  )
}
