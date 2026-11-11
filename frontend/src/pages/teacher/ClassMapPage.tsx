import { useClassResults } from '@/features/teacher/useClassResults'
import type { ClassGaps, ClassProgress, ClassTests, TestResultStatus } from '@/features/teacher/teacherApi'
import { classMap, testStatus } from './content'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
const heading = 'font-heading text-xl leading-7 text-parchment xl:text-[22px]'

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}

function dateTimeLabel(iso: string): string {
  return new Date(iso).toLocaleString('uk-UA', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function Bar({ pct, accent }: { pct: number; accent?: boolean }) {
  return (
    <span className="block h-2 w-full rounded-full bg-line-soft">
      <span
        className={`block h-2 rounded-full ${accent ? 'bg-accent' : 'bg-safe'}`}
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </span>
  )
}

function ProgressSection({ progress }: { progress: ClassProgress | null }) {
  const t = classMap.progress
  const lessons = progress?.lessons ?? []
  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      {lessons.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col">
          {lessons.map((lesson, i) => (
            <li key={lesson.lesson_id} className={`flex flex-col gap-2 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-[15px] leading-[22.5px] font-medium text-parchment">{lesson.title}</p>
                <p className="text-xs text-dim">
                  {lesson.subject_name} · {new Date(lesson.first_date).toLocaleDateString('uk-UA')}
                </p>
              </div>
              <Bar pct={lesson.avg_progress_pct} />
              <p className="text-sm text-muted">
                {t.completed(lesson.students_completed, lesson.students_total)} · {t.avgProgress(lesson.avg_progress_pct)}
              </p>
              <p className="text-sm text-muted">
                {lesson.tests_scored > 0 ? t.tests(lesson.tests_passed, lesson.tests_scored) : t.noTests}
                {lesson.avg_score !== null && ` · ${t.avgScore(lesson.avg_score)}`}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

const statusColor: Record<TestResultStatus, string> = {
  passed: 'text-safe',
  not_passed: 'text-accent',
  closing_soon: 'text-accent',
  pending: 'text-dim',
}

function TestsSection({ tests }: { tests: ClassTests | null }) {
  const t = classMap.tests
  const list = tests?.tests ?? []
  return (
    <section className={card}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <h2 className={heading}>{t.title}</h2>
        {tests && <p className="text-xs text-dim">{t.passScore(tests.pass_score)}</p>}
      </div>
      {list.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        list.map((test) => (
          <details key={test.test_id} className="rounded-2xl border border-line-soft p-4">
            <summary className="cursor-pointer list-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none">
              <p className="text-[15px] leading-[22.5px] font-medium text-parchment">
                {test.lesson_title}: {test.title}
              </p>
              <p className="text-xs text-dim">
                {test.window_hours ? t.window(test.window_hours) : t.noWindow} · {testStatus.passed} {test.counts.passed} ·{' '}
                {testStatus.not_passed} {test.counts.not_passed} · {testStatus.closing_soon} {test.counts.closing_soon} ·{' '}
                {testStatus.pending} {test.counts.pending}
              </p>
            </summary>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="text-xs text-dim">
                    <th scope="col" className="pb-2 font-semibold">Учень</th>
                    <th scope="col" className="pb-2 font-semibold">Статус</th>
                    <th scope="col" className="pb-2 text-right font-semibold">Оцінка</th>
                  </tr>
                </thead>
                <tbody>
                  {test.students.map((student) => (
                    <tr key={student.student_id} className="border-t border-line-soft align-top">
                      <td className="py-2 pr-3 text-sm text-parchment">
                        {[student.display_name, student.last_name].filter(Boolean).join(' ')}
                        {student.is_suspicious && (
                          <span className="block text-xs font-semibold text-accent">{t.suspicious}</span>
                        )}
                      </td>
                      <td className={`py-2 pr-3 text-sm font-semibold ${statusColor[student.status]}`}>
                        {testStatus[student.status]}
                        {student.deadline && student.status !== 'passed' && (
                          <span className="block text-xs font-normal text-dim">{t.deadline(dateTimeLabel(student.deadline))}</span>
                        )}
                      </td>
                      <td className="py-2 text-right text-sm text-muted">
                        {student.score !== null ? `${Math.round(student.score)}%` : '—'}
                        {student.attempts > 0 && <span className="block text-xs text-dim">{t.attempts(student.attempts)}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        ))
      )}
    </section>
  )
}

function GapsSection({ gaps }: { gaps: ClassGaps | null }) {
  const t = classMap.gaps
  const topics = gaps?.topics.filter((topic) => topic.tests_scored > 0) ?? []
  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      {topics.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col">
          {topics.map((topic, i) => (
            <li key={topic.lesson_id} className={`flex flex-col gap-2 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-[15px] leading-[22.5px] font-medium text-parchment">
                  {topic.title} <span className="text-xs text-dim">· {topic.subject_name}</span>
                </p>
                <p className={`text-xs font-semibold ${topic.is_gap ? 'text-accent' : 'text-safe'}`}>
                  {topic.is_gap ? t.gap : t.ok}
                  {topic.avg_score !== null ? ` · ${Math.round(topic.avg_score)}%` : ` · ${t.noScore}`}
                </p>
              </div>
              <Bar pct={topic.avg_score ?? 0} accent={topic.is_gap} />
              {topic.questions.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {topic.questions.slice(0, 3).map((q) => (
                    <li key={q.question_id} className="text-sm text-muted">
                      «{q.prompt}» — {t.question(q.correct_pct, q.correct, q.answered)}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function ClassMapPage() {
  const { progress, tests, gaps, isLoading, isOffline } = useClassResults()

  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="map" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <div className="flex flex-col gap-1">
            <h1 className="font-heading text-2xl leading-[30px] text-parchment">{classMap.title}</h1>
            <p role="status" className="text-sm text-dim">
              {isLoading
                ? classMap.loading
                : progress?.computed_at
                  ? classMap.updated(timeLabel(progress.computed_at))
                  : classMap.notComputed}
            </p>
            {isOffline && <p className="text-sm text-dim">{classMap.offline}</p>}
          </div>
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
            <div className="flex flex-col gap-5 xl:min-w-0 xl:flex-1 xl:gap-6">
              <TestsSection tests={tests} />
              <ProgressSection progress={progress} />
            </div>
            <div className="xl:w-[420px] xl:shrink-0">
              <GapsSection gaps={gaps} />
            </div>
          </div>
        </main>
      </div>
      <TeacherTabs activeId="more" />
    </div>
  )
}
