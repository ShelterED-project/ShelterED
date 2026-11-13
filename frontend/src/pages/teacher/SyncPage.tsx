import { useEffect, useState } from 'react'
import iconServer from '@/assets/teacher/server-wifi.svg'
import { useClassReadiness } from '@/features/teacher/useClassReadiness'
import type { DayReadiness, ReadinessDay } from '@/features/teacher/useClassReadiness'
import { pluralUk } from '@/shared/lib/plural'
import Spinner from '@/shared/ui/Spinner'
import { localServer, qrSync, syncPage } from './content'
import ComingSoonCard from './sections/ComingSoonCard'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
const heading = 'font-heading text-xl leading-7 text-parchment xl:text-[22px]'

/** Дата школи (YYYY-MM-DD) як «пт, 14 лист.». Полудень UTC: день не зсувається поясом. */
function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'short' })
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} КБ` : `${(bytes / 1024 / 1024).toFixed(1)} МБ`
}

function timeLabel(iso: string | number): string {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === new Date().toDateString()) return `сьогодні о ${time}`
  return `${date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })}, ${time}`
}

const stateStyle: Record<DayReadiness, string> = {
  ready: 'bg-safe/15 text-safe',
  missing: 'bg-accent-soft text-accent',
  unassigned: 'bg-accent-soft text-accent',
  free: 'bg-line-soft text-dim',
}

function DayRow({ day, isToday }: { day: ReadinessDay; isToday: boolean }) {
  const t = syncPage.readiness
  return (
    <li className="flex items-start gap-3 border-t border-line-soft py-3 first:border-t-0">
      <div className="min-w-0 flex-1">
        <p className={`text-[15px] leading-[22.5px] font-medium ${day.state === 'free' ? 'text-dim' : 'text-parchment'}`}>
          {dayLabel(day.date)}
          {isToday && <span className="ml-2 text-xs font-semibold text-accent">{t.today}</span>}
        </p>
        {day.lessons > 0 && (
          <p className="text-xs text-dim">
            {t.lessons(day.lessons, pluralUk(day.lessons, ['урок', 'уроки', 'уроків']))}
            {day.pack && ` · ${t.built(sizeLabel(day.pack.size_bytes), timeLabel(day.pack.built_at))}`}
          </p>
        )}
        {day.state === 'missing' && <p className="text-xs text-accent">{t.missingHint}</p>}
      </div>
      <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold ${stateStyle[day.state]}`}>
        {t.state[day.state]}
      </span>
    </li>
  )
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])
  return online
}

export default function SyncPage() {
  const { days, isLoading, isOffline, updatedAt, isFetching, refresh } = useClassReadiness()
  const online = useOnline()
  const t = syncPage
  // Дату фіксуємо при відкритті сторінки: позначка «сьогодні» не стрибає між рендерами.
  const [today] = useState(() => new Date().toLocaleDateString('sv-SE'))
  const schoolDays = (days ?? []).filter((d) => d.state !== 'free')
  const readyDays = schoolDays.filter((d) => d.state === 'ready').length

  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="sync" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <div className="flex flex-col gap-1">
            <h1 className="font-heading text-2xl leading-[30px] text-parchment">{t.title}</h1>
            <p className="text-sm text-dim">{t.subtitle}</p>
          </div>

          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
            <section className={`${card} xl:min-w-0 xl:flex-1`}>
              <div className="flex flex-col gap-1">
                <h2 className={heading}>{t.readiness.title}</h2>
                <p className="text-sm text-dim">{t.readiness.hint}</p>
              </div>
              {!days ? (
                <p role="status" className="text-sm text-muted">
                  {isLoading ? t.readiness.loading : t.readiness.offline}
                </p>
              ) : (
                <>
                  <p
                    role="status"
                    className={`text-[15px] font-semibold ${readyDays === schoolDays.length ? 'text-safe' : 'text-accent'}`}
                  >
                    {readyDays === schoolDays.length ? t.readiness.allReady : t.readiness.summary(readyDays, schoolDays.length)}
                  </p>
                  <ul>
                    {days.map((day) => (
                      <DayRow key={day.date} day={day} isToday={day.date === today} />
                    ))}
                  </ul>
                </>
              )}
            </section>

            <div className="flex flex-col gap-5 xl:w-[400px] xl:shrink-0 xl:gap-6">
              <section className={card}>
                <h2 className={heading}>{t.connection.title}</h2>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <div>
                    <dt className="text-xs text-dim">{t.connection.internet}</dt>
                    <dd className={`text-sm font-semibold ${online ? 'text-parchment' : 'text-accent'}`}>
                      {online ? t.connection.yes : t.connection.no}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-dim">{t.connection.server}</dt>
                    <dd className={`text-sm font-semibold ${isOffline ? 'text-accent' : 'text-parchment'}`}>
                      {isOffline ? t.connection.down : t.connection.ok}
                    </dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-xs text-dim">{t.connection.updated}</dt>
                    <dd className="text-sm font-semibold text-parchment">
                      {updatedAt ? timeLabel(updatedAt) : t.connection.never}
                    </dd>
                  </div>
                </dl>
                <button
                  type="button"
                  onClick={refresh}
                  disabled={isFetching}
                  aria-busy={isFetching}
                  className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60"
                >
                  {isFetching && <Spinner />}
                  {isFetching ? t.connection.refreshing : t.connection.refresh}
                </button>
              </section>

              <ComingSoonCard title={localServer.title} soon={localServer.soon} text={localServer.text} icon={iconServer} />
              <ComingSoonCard title={qrSync.title} soon={qrSync.soon} text={qrSync.text} />
            </div>
          </div>
        </main>
      </div>
      <TeacherTabs activeId="more" />
    </div>
  )
}
