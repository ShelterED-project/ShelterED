import { useCurrentUser } from '@/features/auth/useCurrentUser'
import type { StudentProgress, StudentTest, StudentTestStatus } from '@/features/student/studentApi'
import { useStudentProgress } from '@/features/student/useStudentProgress'
import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { mePage } from './content'
import StudentHeader from './sections/StudentHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
const heading = 'font-heading text-xl leading-7 text-parchment xl:text-[22px]'

function whenLabel(iso: string): string {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === new Date().toDateString()) return `сьогодні о ${time}`
  return `${date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })}, ${time}`
}

/** День школи (YYYY-MM-DD) як «пн». Полудень UTC: день не зсувається поясом. */
function weekday(day: string): string {
  return new Date(`${day}T12:00:00Z`).toLocaleDateString('uk-UA', { weekday: 'short' })
}

function StudyCard({ study }: { study: StudentProgress['study'] }) {
  const t = mePage.study
  const max = Math.max(1, ...study.days.map((d) => d.minutes))
  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-surface-2 p-4">
          <dt className="text-xs text-dim">{t.week}</dt>
          <dd className="font-heading text-[28px] leading-[34px] text-accent">{t.minutes(study.last_7_days_minutes)}</dd>
        </div>
        <div className="rounded-2xl bg-surface-2 p-4">
          <dt className="text-xs text-dim">{t.total}</dt>
          <dd className="font-heading text-[28px] leading-[34px] text-parchment">{t.minutes(study.total_minutes)}</dd>
        </div>
      </dl>
      {/* Хвилини по днях: стовпчик на день, підпис значення над ним. */}
      <ol className="flex h-36 items-end gap-2" aria-label={t.week}>
        {study.days.map((d) => (
          <li key={d.day} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
            <span className="text-xs text-muted">{d.minutes > 0 ? d.minutes : ''}</span>
            <span
              className={`w-full max-w-10 rounded-t-md ${d.minutes > 0 ? 'bg-accent' : 'bg-line-soft'}`}
              style={{ height: `${Math.max(4, (d.minutes / max) * 100)}%` }}
              aria-label={`${weekday(d.day)}: ${t.minutes(d.minutes)}`}
            />
            <span className="text-xs text-dim">{weekday(d.day)}</span>
          </li>
        ))}
      </ol>
      <p className="text-xs text-dim">{t.hint}</p>
    </section>
  )
}

/** Спершу те, що треба зробити: вікно закривається, не здано; потім не складено й складено. */
const statusOrder: Record<StudentTestStatus, number> = { closing_soon: 0, pending: 1, not_passed: 2, passed: 3 }
const statusColor: Record<StudentTestStatus, string> = {
  closing_soon: 'text-accent',
  pending: 'text-muted',
  not_passed: 'text-accent',
  passed: 'text-safe',
}

function TestsCard({ tests }: { tests: StudentTest[] }) {
  const t = mePage.tests
  const sorted = [...tests].sort(
    (a, b) => statusOrder[a.status] - statusOrder[b.status] || (a.deadline ?? '').localeCompare(b.deadline ?? ''),
  )
  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      {sorted.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col">
          {sorted.map((test, i) => (
            <li key={test.test_id} className={`flex items-start gap-3 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
              <div className="min-w-0 flex-1">
                <p className="text-[15px] leading-[22.5px] font-medium text-parchment">{test.title}</p>
                <p className="text-xs text-dim">
                  {test.status === 'passed' ? t.attempts(test.attempts) : test.deadline ? t.deadline(whenLabel(test.deadline)) : t.noWindow}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className={`text-sm font-semibold ${statusColor[test.status]}`}>{t.status[test.status]}</p>
                {test.score !== null && <p className="text-sm text-muted">{Math.round(test.score)}%</p>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function LessonsCard({ lessons }: { lessons: StudentProgress['lessons'] }) {
  const t = mePage.lessons
  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      {lessons.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col">
          {lessons.map((lesson, i) => (
            <li key={lesson.lesson_id} className={`flex flex-col gap-2 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 text-[15px] leading-[22.5px] font-medium text-parchment">
                  {lesson.title} <span className="text-xs text-dim">· {lesson.subject_name}</span>
                </p>
                <p className={`shrink-0 text-xs font-semibold ${lesson.progress_pct >= 100 ? 'text-safe' : 'text-muted'}`}>
                  {lesson.progress_pct >= 100 ? t.done : `${lesson.progress_pct}%`}
                </p>
              </div>
              <span className="block h-2 rounded-full bg-line-soft">
                <span
                  className={`block h-2 rounded-full ${lesson.progress_pct >= 100 ? 'bg-safe' : 'bg-accent'}`}
                  style={{ width: `${Math.min(100, Math.max(0, lesson.progress_pct))}%` }}
                />
              </span>
              <p className="text-xs text-dim">
                {t.modules(lesson.modules_done, lesson.modules_total)}
                {lesson.study_minutes > 0 && ` · ${mePage.study.minutes(lesson.study_minutes)}`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function MePage() {
  const pending = useOutboxCount()
  const user = useCurrentUser()
  const { progress, isLoading, isOffline } = useStudentProgress()

  const status = isLoading
    ? mePage.loading
    : !progress
      ? isOffline
        ? mePage.offlineEmpty
        : mePage.notComputed
      : progress.computed_at
        ? mePage.updated(whenLabel(progress.computed_at))
        : mePage.notComputed

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="me" />
      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader pending={pending} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <div className="flex flex-col gap-1">
            <h1 className="font-heading text-2xl leading-[30px] text-parchment">{user?.fullName ?? mePage.title}</h1>
            <p role="status" className="text-sm text-dim">
              {status}
            </p>
            {isOffline && progress && <p className="text-sm text-dim">{mePage.offline}</p>}
          </div>
          {progress && (
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
              <div className="flex flex-col gap-5 xl:w-[400px] xl:shrink-0 xl:gap-6">
                <StudyCard study={progress.study} />
                <TestsCard tests={progress.tests} />
              </div>
              <div className="xl:min-w-0 xl:flex-1">
                <LessonsCard lessons={progress.lessons} />
              </div>
            </div>
          )}
        </main>
      </div>
      <StudentTabs activeId="me" />
    </div>
  )
}
