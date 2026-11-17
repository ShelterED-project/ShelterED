import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { useAlertJournalQuery } from '@/features/admin/adminApi'
import { downloadAlertsCsv } from '@/features/admin/alertsCsv'
import { kyivDate } from '@/features/admin/useSchoolOverview'
import { useClassesQuery } from '@/features/teacher/teacherApi'
import { alarms as t, loading, offline } from './content'
import AdminHeader from './sections/AdminHeader'
import AdminSidebar from './sections/AdminSidebar'
import AdminTabs from './sections/AdminTabs'
import AlarmLog from './sections/AlarmLog'
import CreateUserDialog from './sections/CreateUserDialog'
import MobileGreeting from './sections/MobileGreeting'

/** Період за замовчуванням: останні 30 днів. */
const DEFAULT_DAYS = 30

const dateInput =
  'h-11 rounded-[10px] border border-line bg-surface px-3 text-sm text-parchment [color-scheme:dark] focus:border-accent focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none'

export default function AdminAlarmsPage() {
  const [creating, setCreating] = useState(false)
  const [today] = useState(() => kyivDate(new Date()))
  const [range, setRange] = useState(() => ({
    from: kyivDate(new Date(Date.now() - (DEFAULT_DAYS - 1) * 24 * 60 * 60 * 1000)),
    to: kyivDate(new Date()),
  }))
  const [draft, setDraft] = useState(range)
  const journal = useAlertJournalQuery(range, { refetchOnMountOrArgChange: true })
  const classes = useClassesQuery()
  const classNames = new Map((classes.data ?? []).map((c) => [c.id, c.name]))
  const alerts = journal.data ?? []

  function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    // Переплутані дати міняємо місцями, а не показуємо помилку.
    setRange(draft.from <= draft.to ? draft : { from: draft.to, to: draft.from })
  }

  return (
    <div className="flex min-h-screen">
      <AdminSidebar activeId="alarms" />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader onAddUser={() => setCreating(true)} title={t.title} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting title={t.title} />
          <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-sm font-semibold text-parchment">
              {t.range.from}
              <input
                type="date"
                value={draft.from}
                max={today}
                onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))}
                className={dateInput}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold text-parchment">
              {t.range.to}
              <input
                type="date"
                value={draft.to}
                max={today}
                onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))}
                className={dateInput}
              />
            </label>
            <button
              type="submit"
              disabled={!draft.from || !draft.to}
              className="h-11 rounded-[10px] bg-accent px-5 text-sm font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
            >
              {t.range.apply}
            </button>
          </form>

          {journal.isLoading && (
            <p role="status" className="text-sm text-muted">
              {loading}
            </p>
          )}
          {journal.isError && (
            <p role="status" className="text-sm text-muted">
              {offline}
            </p>
          )}

          <AlarmLog
            alerts={alerts}
            classNames={classNames}
            actions={
              <button
                type="button"
                disabled={alerts.length === 0}
                onClick={() => downloadAlertsCsv(alerts, classNames, t.csvName(range.from, range.to))}
                className="h-10 shrink-0 rounded-[10px] border border-line-strong px-4 text-sm font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60"
              >
                {t.export}
              </button>
            }
          />
        </main>
      </div>
      <AdminTabs activeId="alarms" />
      <CreateUserDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  )
}
