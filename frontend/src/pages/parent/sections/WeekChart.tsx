import type { StudentProgress } from '@/features/student/studentApi'
import { week } from '../content'

/** Висота найвищого стовпчика, px. */
const MAX_BAR = 150

function weekday(day: string): string {
  // day — дата «2026-11-17» без поясу: читаємо як місцеву, щоб не з'їхав день.
  const [y, m, d] = day.split('-').map(Number)
  const text = new Date(y, m - 1, d).toLocaleDateString('uk-UA', { weekday: 'short' })
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export default function WeekChart({ progress, className = '' }: { progress: StudentProgress | null; className?: string }) {
  const days = progress?.study.days ?? []
  const max = Math.max(1, ...days.map((d) => d.minutes))
  const empty = days.every((d) => d.minutes === 0)

  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
          {week.title}
        </h2>
        <p className="text-xs text-dim">{week.range}</p>
      </div>

      {empty ? (
        <p className="text-sm text-muted">{week.empty}</p>
      ) : (
        <div className="flex items-end gap-2 px-1 md:gap-5">
          {days.map((d) => (
            <div key={d.day} className="flex min-w-0 flex-1 flex-col items-center gap-2">
              <span className="text-xs text-muted">{d.minutes > 0 ? d.minutes : ''}</span>
              <div role="img" aria-label={week.minutes(weekday(d.day), d.minutes)} className="flex h-[150px] w-11 max-w-full flex-col justify-end">
                <div
                  className={`w-full rounded-md ${d.minutes > 0 ? 'bg-accent' : 'bg-line-strong'}`}
                  style={{ height: Math.max(4, Math.round((d.minutes / max) * MAX_BAR)) }}
                />
              </div>
              <span className="text-xs text-dim">{weekday(d.day)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
