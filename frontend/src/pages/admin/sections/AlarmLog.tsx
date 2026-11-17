import type { ReactNode } from 'react'
import type { Alert } from '@/features/alerts/alertsApi'
import { alertMinutes } from '@/features/admin/useSchoolOverview'
import { shortDateLabel, timeLabel } from '@/shared/lib/date'
import { alarms as t, minutesLabel } from '../content'

type Props = {
  alerts: Alert[]
  classNames: Map<string, string>
  title?: string
  /** Кнопки праворуч від заголовка (експорт, посилання на весь журнал) */
  actions?: ReactNode
}

function scope(alert: Alert, classNames: Map<string, string>): string {
  if (alert.class_id) return classNames.get(alert.class_id) ?? '—'
  return alert.location_title ?? t.wholeSchool
}

function kind(alert: Alert): string {
  const parts = [alert.source === 'manual' ? t.manual : t.fromApi]
  if (alert.is_drill) parts.push(t.drill)
  return parts.join(', ')
}

export default function AlarmLog({ alerts, classNames, title = t.title, actions }: Props) {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{title}</h2>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      {alerts.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="text-xs text-dim">
                <th scope="col" className="pb-2 font-semibold">{t.columns.date}</th>
                <th scope="col" className="pb-2 font-semibold">{t.columns.start}</th>
                <th scope="col" className="hidden pb-2 font-semibold md:table-cell">{t.columns.end}</th>
                <th scope="col" className="pb-2 font-semibold">{t.columns.duration}</th>
                <th scope="col" className="hidden pb-2 font-semibold md:table-cell">{t.columns.scope}</th>
                <th scope="col" className="hidden pb-2 font-semibold lg:table-cell">{t.columns.kind}</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => {
                const ongoing = alert.ended_at === null
                return (
                  <tr key={alert.id} className="border-t border-line-soft text-sm leading-5">
                    <td className="py-3 pr-3 whitespace-nowrap text-parchment">{shortDateLabel(alert.started_at)}</td>
                    <td className="py-3 pr-3 whitespace-nowrap text-parchment">{timeLabel(alert.started_at)}</td>
                    <td className="hidden py-3 pr-3 whitespace-nowrap text-parchment md:table-cell">
                      {alert.ended_at ? timeLabel(alert.ended_at) : '—'}
                    </td>
                    <td className={`py-3 pr-3 font-semibold whitespace-nowrap ${ongoing ? 'text-accent' : 'text-parchment'}`}>
                      {ongoing ? t.ongoing : minutesLabel(alertMinutes(alert))}
                    </td>
                    <td className="hidden py-3 pr-3 whitespace-nowrap text-dim md:table-cell">{scope(alert, classNames)}</td>
                    <td className="hidden py-3 whitespace-nowrap text-dim lg:table-cell">{kind(alert)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
