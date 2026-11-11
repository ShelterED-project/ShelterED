import { useTeacherSchedule } from '@/features/teacher/useTeacherSchedule'
import { schedule, schedulePage } from './content'
import ScheduleList from './sections/ScheduleList'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

/** Дата школи (YYYY-MM-DD) як «середа, 11 листопада». Полудень UTC: день не зсувається поясом. */
function dayLabel(date: string): string {
  const text = new Date(`${date}T12:00:00Z`).toLocaleDateString('uk-UA', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export default function SchedulePage() {
  const { days, isLoading, isOffline } = useTeacherSchedule(schedulePage.days)

  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="schedule" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <div className="flex flex-col gap-1">
            <h1 className="font-heading text-2xl leading-[30px] text-parchment">{schedulePage.title}</h1>
            <p className="text-sm text-dim">{schedulePage.subtitle}</p>
          </div>
          {!days ? (
            <p role="status" className="text-sm text-muted">
              {isLoading ? schedule.loading : isOffline ? schedule.offline : schedule.empty}
            </p>
          ) : (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3 xl:gap-6">
              {days.map((day, i) => (
                <section
                  key={day.date}
                  className={`flex flex-col gap-2 rounded-[22px] border bg-surface p-5 md:p-6 ${
                    i === 0 ? 'border-accent/40' : 'border-line'
                  }`}
                >
                  <h2 className="font-heading text-lg leading-7 text-parchment">
                    {dayLabel(day.date)}
                    {i === 0 && <span className="ml-2 text-xs font-semibold text-accent">{schedulePage.today}</span>}
                  </h2>
                  {day.rows.length > 0 ? (
                    <ScheduleList rows={day.rows} />
                  ) : (
                    <p className="text-sm text-dim">{schedulePage.noLessons}</p>
                  )}
                </section>
              ))}
            </div>
          )}
        </main>
      </div>
      <TeacherTabs activeId="more" />
    </div>
  )
}
