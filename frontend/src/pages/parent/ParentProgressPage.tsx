import { useChildDashboard, useChildWellbeing } from '@/features/parent/useChildDashboard'
import type { WellbeingParent } from '@/features/parent/parentApi'
import { childName, useParentChildren } from '@/features/parent/useParentChildren'
import type { KnowledgeMap, StudentProgress, StudentTestStatus } from '@/features/student/studentApi'
import { dateTimeLabel, shortDateLabel } from '@/shared/lib/date'
import { loading, offline, progressPage as t, testStatus } from './content'
import LinkChild from './sections/LinkChild'
import MobileGreeting from './sections/MobileGreeting'
import MobileHeader from './sections/MobileHeader'
import MobileTabs from './sections/MobileTabs'
import Sidebar from './sections/Sidebar'
import TopBar from './sections/TopBar'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
const heading = 'font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]'

const statusColor: Record<StudentTestStatus, string> = {
  passed: 'text-safe',
  not_passed: 'text-danger',
  closing_soon: 'text-accent',
  pending: 'text-dim',
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

function LessonsCard({ progress }: { progress: StudentProgress | null }) {
  const lessons = progress?.lessons ?? []
  return (
    <section className={card}>
      <h2 className={heading}>{t.lessons.title}</h2>
      {lessons.length === 0 ? (
        <p className="text-sm text-muted">{t.lessons.empty}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {lessons.map((lesson) => (
            <li key={lesson.lesson_id} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 text-[15px] font-semibold text-parchment">
                  {lesson.title}
                  <span className="block text-xs font-normal text-dim">{lesson.subject_name}</span>
                </p>
                <p className="shrink-0 text-right text-xs text-muted">
                  {t.lessons.modules(lesson.modules_done, lesson.modules_total)}
                  {lesson.study_minutes > 0 && <span className="block text-dim">{t.lessons.minutes(lesson.study_minutes)}</span>}
                </p>
              </div>
              <Bar pct={lesson.progress_pct} accent={lesson.progress_pct < 100} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function TestsCard({ progress }: { progress: StudentProgress | null }) {
  const tests = progress?.tests ?? []
  return (
    <section className={card}>
      <h2 className={heading}>{t.tests.title}</h2>
      {tests.length === 0 ? (
        <p className="text-sm text-muted">{t.tests.empty}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-line-soft">
          {tests.map((test) => (
            <li key={test.test_id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="text-[15px] font-semibold text-parchment">{test.title}</p>
                <p className={`text-sm font-semibold ${statusColor[test.status]}`}>
                  {testStatus[test.status]}
                  {test.deadline && test.status !== 'passed' && (
                    <span className="ml-2 font-normal text-dim">{t.tests.deadline(dateTimeLabel(test.deadline))}</span>
                  )}
                </p>
              </div>
              <p className="shrink-0 text-right text-sm font-semibold text-parchment">
                {test.score !== null ? t.tests.score(test.score) : '—'}
                {test.attempts > 0 && <span className="block text-xs font-normal text-dim">{t.tests.attempts(test.attempts)}</span>}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function MapCard({ knowledgeMap }: { knowledgeMap: KnowledgeMap | null }) {
  const subjects = knowledgeMap?.subjects ?? []
  return (
    <section className={card}>
      <h2 className={heading}>{t.map.title}</h2>
      {subjects.length === 0 ? (
        <p className="text-sm text-muted">{t.map.empty}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {subjects.map((subject) => (
            <li key={subject.subject_id} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-[15px] font-semibold text-parchment">
                  {subject.name}
                  {subject.is_gap && <span className="ml-2 text-xs font-semibold text-accent">{t.map.gap}</span>}
                </p>
                <p className="shrink-0 text-xs text-muted">{t.map.lessons(subject.lessons_completed, subject.lessons_total)}</p>
              </div>
              <Bar pct={subject.lessons_total ? (subject.lessons_completed / subject.lessons_total) * 100 : 0} accent={subject.is_gap} />
              {subject.avg_score !== null && <p className="text-xs text-dim">{t.map.score(subject.avg_score)}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function WellbeingCard({ wellbeing, isOffline }: { wellbeing: WellbeingParent | null; isOffline: boolean }) {
  return (
    <section className={card}>
      <div>
        <h2 className={heading}>{t.wellbeing.title}</h2>
        {wellbeing && (
          <p className="mt-1 text-xs text-dim">
            {t.wellbeing.week(shortDateLabel(wellbeing.week_from), shortDateLabel(wellbeing.week_to))}
          </p>
        )}
      </div>
      {wellbeing ? (
        <>
          <p className="text-[15px] leading-6 text-parchment">{wellbeing.summary}</p>
          {wellbeing.gentle_note && <p className="text-sm leading-5 text-muted">{wellbeing.gentle_note}</p>}
          {wellbeing.tips.length > 0 && (
            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-parchment">{t.wellbeing.tipsTitle}</h3>
              <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-5 text-muted">
                {wellbeing.tips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        isOffline && <p className="text-sm text-muted">{t.wellbeing.offline}</p>
      )}
      <p className="text-xs leading-5 text-dim">{t.wellbeing.about}</p>
    </section>
  )
}

export default function ParentProgressPage() {
  const { children, selected, select, isLoading, isOffline: childrenOffline } = useParentChildren()
  const childId = selected?.child_id ?? null
  const dashboard = useChildDashboard(childId)
  const { wellbeing, isOffline: wellbeingOffline } = useChildWellbeing(childId)

  return (
    <div className="flex min-h-screen">
      <Sidebar activeId="progress" />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        <TopBar childList={children} selected={selected} onChange={select} title={t.title} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:gap-6 md:px-10 md:py-8">
          <MobileGreeting childList={children} selected={selected} onChange={select} title={t.title} />
          {selected && <p className="text-sm text-dim">{t.subtitle(childName(selected))}</p>}

          {isLoading && (
            <p role="status" className="text-sm text-muted">
              {loading}
            </p>
          )}
          {(childrenOffline || (selected && dashboard.isOffline)) && (
            <p role="status" className="text-sm text-muted">
              {offline}
            </p>
          )}
          {!isLoading && children.length === 0 && <LinkChild empty onLinked={select} />}

          {selected && (
            <div className="flex flex-col gap-5 md:gap-6 xl:flex-row xl:items-start">
              <div className="flex flex-col gap-5 md:gap-6 xl:min-w-0 xl:flex-1">
                <LessonsCard progress={dashboard.progress} />
                <TestsCard progress={dashboard.progress} />
              </div>
              <div className="flex flex-col gap-5 md:gap-6 xl:w-[400px] xl:shrink-0">
                <MapCard knowledgeMap={dashboard.knowledgeMap} />
                <WellbeingCard wellbeing={wellbeing} isOffline={wellbeingOffline} />
              </div>
            </div>
          )}
        </main>
      </div>
      <MobileTabs activeId="progress" />
    </div>
  )
}
