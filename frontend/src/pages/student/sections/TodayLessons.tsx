import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { skipToken } from '@reduxjs/toolkit/query/react'
import { useLiveQuery } from 'dexie-react-hooks'
import iconBook from '@/assets/student/book.svg'
import iconDone from '@/assets/student/check-20.svg'
import iconDownload from '@/assets/student/lessons-download.svg'
import iconTest from '@/assets/student/lessons-test-check.svg'
import { useAppSelector } from '@/app/hooks'
import { useNextPackDay, useTodayPack } from '@/features/packs/usePacks'
import type { TodayLesson } from '@/features/packs/usePacks'
import { useKnowledgeMapQuery } from '@/features/student/studentApi'
import type { StudentProgress, StudentTest } from '@/features/student/studentApi'
import { useStudentProgress } from '@/features/student/useStudentProgress'
import { db } from '@/shared/db/db'
import type { LessonProgressRecord } from '@/shared/db/types'
import { timeLabel } from '@/shared/lib/date'
import { navRoutes, todayLessons as t } from '../content'

type View = 'days' | 'subjects'
type Day = 'today' | 'next'

const HOUR_MS = 3_600_000

/** «2026-11-20» → дата за місцевим часом (без зсуву UTC). */
function packDate(date: string): Date {
  const [y, m, d] = date.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function weekday(date: Date): string {
  return date.toLocaleDateString('uk-UA', { weekday: 'long' })
}

function nextDayTitle(date: string): string {
  const day = packDate(date)
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  if (day.toDateString() === tomorrow.toDateString()) return t.tomorrow(weekday(day))
  const text = day.toLocaleDateString('uk-UA', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Пройдено: за локальним прогресом (ще не синхронізованим) або за сервером, як і на маршруті. */
function lessonProgress(item: TodayLesson, local: Set<string>, progress: StudentProgress | null) {
  const { modules, tests } = item.lesson
  const server = progress?.lessons.find((l) => l.lesson_id === item.lesson.id)
  const localModules = modules.filter((m) => local.has(m.id)).length
  const modulesDone =
    (server?.progress_pct ?? 0) >= 100
      ? modules.length
      : Math.min(modules.length, Math.max(localModules, server?.modules_done ?? 0))
  const testsDone = tests.every(
    (test) => local.has(test.id) || (progress?.tests.find((x) => x.test_id === test.id)?.attempts ?? 0) > 0,
  )
  return {
    pct: modules.length === 0 ? 0 : Math.round((modulesDone / modules.length) * 100),
    done: modules.length > 0 && modulesDone === modules.length && testsDone,
  }
}

function lessonMeta(item: TodayLesson): string {
  const { modules, tests } = item.lesson
  const windowTest = tests.find((test) => test.window_enabled && test.window_hours)
  const extra = windowTest?.window_hours
    ? t.withWindow(windowTest.window_hours)
    : tests.length > 0
      ? t.withTest
      : t.minutes(item.minutes)
  return `${t.modules(modules.length)} · ${extra}`
}

function LessonRow({
  item,
  day,
  subject,
  local,
  progress,
}: {
  item: TodayLesson
  day: Day
  subject: string | null
  local: Set<string>
  progress: StudentProgress | null
}) {
  const { pct, done } = lessonProgress(item, local, progress)
  const isNow = day === 'today' && item.status === 'now'

  let status: ReactNode
  if (done) status = <img src={iconDone} alt={t.done} width={20} height={20} className="shrink-0" />
  else if (isNow) {
    status = (
      <span className="shrink-0 rounded-md bg-accent px-2 py-0.5 text-[11px] leading-[16.5px] font-bold text-oil">
        {t.now}
      </span>
    )
  } else {
    status = (
      <span className="shrink-0 text-[11px] leading-[16.5px] text-dim">
        {day === 'today' ? t.offline : t.inBackpack}
      </span>
    )
  }

  const body = (
    <>
      <span className="hidden w-12 shrink-0 text-sm leading-5 text-dim md:block">{item.startsAt}</span>
      <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft">
        <img src={iconBook} alt="" width={20} height={20} />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        {/* На телефоні час переходить у рядок предмета: окремої колонки часу там немає. */}
        <span className="text-xs leading-4 text-dim">
          <span className="md:hidden">{[subject, item.startsAt].filter(Boolean).join(' · ')}</span>
          <span className="hidden md:inline">{subject}</span>
        </span>
        <span className="truncate text-[15px] leading-[22.5px] font-semibold text-parchment">{item.lesson.title}</span>
        <span className={`pt-0.5 text-xs leading-4 text-dim ${pct > 0 ? 'pb-2' : ''}`}>{lessonMeta(item)}</span>
        {pct > 0 && (
          <span
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label={item.lesson.title}
            className="block h-1.5 w-60 max-w-full rounded-full bg-line-soft"
          >
            <span className="block h-1.5 rounded-full bg-accent" style={{ width: `${pct}%` }} />
          </span>
        )}
      </span>
      {status}
    </>
  )

  const className = `flex items-center gap-4 rounded-2xl border p-4 ${
    isNow ? 'border-accent/50 bg-surface-2' : 'border-line bg-surface'
  }`
  // Урок іншого дня відкрити не можна: програвач бере уроки з сьогоднішнього пакета.
  return day === 'today' ? (
    <Link
      to={`/student/lesson?lesson=${item.lesson.id}`}
      className={`${className} hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none`}
    >
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  )
}

type Row = { item: TodayLesson; day: Day; subject: string | null }

function RowGroup({
  title,
  rows,
  local,
  progress,
  empty,
}: {
  title: string
  rows: Row[]
  local: Set<string>
  progress: StudentProgress | null
  empty?: string
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment">{title}</h2>
      {rows.length === 0 && empty && <p className="text-sm text-muted">{empty}</p>}
      <ul className="flex flex-col gap-2.5">
        {rows.map((row) => (
          <li key={`${row.day}-${row.item.key}`}>
            <LessonRow item={row.item} day={row.day} subject={row.subject} local={local} progress={progress} />
          </li>
        ))}
      </ul>
    </section>
  )
}

function Backpack({ count, builtAt }: { count: number | null; builtAt: string | null }) {
  return (
    <section className="flex flex-col items-start gap-4 rounded-[22px] border border-line bg-surface-2 p-5 md:flex-row md:items-center">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-accent-soft">
        <img src={iconDownload} alt="" width={24} height={24} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="text-base leading-6 font-semibold text-parchment">
          {count === null ? t.backpackMissing : t.backpackReady}
        </p>
        <p className="text-xs leading-4 text-dim">{count === null ? t.backpackMissingText : t.backpackText(count)}</p>
      </div>
      {builtAt && <p className="shrink-0 text-xs leading-4 text-dim">{t.updated(timeLabel(builtAt))}</p>}
    </section>
  )
}

function timeLeft(deadline: string, now: number): string {
  const hours = Math.max(1, Math.floor((Date.parse(deadline) - now) / HOUR_MS))
  return hours < 48 ? t.windowTests.hoursLeft(hours) : t.windowTests.daysLeft(Math.floor(hours / 24))
}

function until(deadline: string): string {
  const date = new Date(deadline)
  return t.windowTests.until(`${date.toLocaleDateString('uk-UA', { weekday: 'short' })} ${timeLabel(deadline)}`)
}

/** Тести з відкритим вікном за прогресом сервера (останній відомий, працює й офлайн). */
function WindowTests({ tests, subjectOf }: { tests: StudentTest[]; subjectOf: (lessonId: string) => string | null }) {
  const [now] = useState(() => Date.now())
  const open = tests.filter(
    (test): test is StudentTest & { deadline: string } =>
      test.deadline !== null &&
      Date.parse(test.deadline) > now &&
      (test.status === 'pending' || test.status === 'closing_soon'),
  )

  return (
    <section className="flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-6">
      <h2 className="font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">{t.windowTests.title}</h2>
      {open.length === 0 ? (
        <p className="text-sm text-muted">{t.windowTests.empty}</p>
      ) : (
        <ul className="flex flex-col pt-1">
          {open.map((test, i) => (
            <li
              key={test.test_id}
              className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}
            >
              <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2">
                <img src={iconTest} alt="" width={20} height={20} />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm leading-5 font-semibold text-parchment">{test.title}</span>
                <span className="text-xs leading-4 text-dim">
                  {[subjectOf(test.lesson_id), until(test.deadline)].filter(Boolean).join(' · ')}
                </span>
              </span>
              <span className="shrink-0 text-xs leading-4 font-semibold text-accent">
                {timeLeft(test.deadline, now)}
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs leading-4 text-dim">{t.windowTests.note}</p>
    </section>
  )
}

/** Предмети-прогалини з мапи знань (потрібна мережа; без неї блок не показуємо). */
function Gaps() {
  const studentId = useAppSelector((s) => s.auth.session?.user.id)
  const { data } = useKnowledgeMapQuery(studentId ?? skipToken)
  const gaps = (data?.subjects ?? []).filter((subject) => subject.is_gap)
  if (gaps.length === 0) return null

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-6">
      <h2 className="font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">{t.gaps.title}</h2>
      <ul className="flex flex-col gap-3">
        {gaps.map((gap) => (
          <li key={gap.subject_id} className="flex items-center gap-3">
            <span className="size-10 shrink-0 rounded-full border-2 border-dashed border-muted" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-sm leading-5 font-semibold text-parchment">{gap.name}</span>
              <span className="text-xs leading-4 text-dim">
                {t.gaps.lessons(gap.lessons_completed, gap.lessons_total)}
              </span>
            </span>
            <Link
              to={navRoutes.me ?? '/student/me'}
              className="flex h-10 shrink-0 items-center rounded-[10px] border border-line-strong px-3 text-sm leading-5 font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            >
              {t.gaps.toMap}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

const chipBase =
  'flex h-10 shrink-0 items-center rounded-full border px-4 text-sm leading-5 font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none'

/**
 * «Мої уроки»: Рюкзак, уроки сьогодні й наступного дня (з фільтром за предметом і групуванням
 * за днями чи предметами), тести з вікном і пропущені теми. Уроки й прогрес — з пристрою.
 */
export default function TodayLessons() {
  const today = useTodayPack()
  const next = useNextPackDay()
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  const records = useLiveQuery(
    () => (userId ? db.userProgress.where('user_id').equals(userId).toArray() : []),
    [userId],
  )
  const { progress } = useStudentProgress()
  const [subject, setSubject] = useState<string | null>(null)
  const [view, setView] = useState<View>('days')
  const [todayName] = useState(() => weekday(new Date()))

  const local = new Set((records ?? []).map((r: LessonProgressRecord) => r.id))
  // Назви предметів у пакеті немає: беремо з прогресу сервера (для нових уроків ще невідома).
  const subjects = new Map((progress?.lessons ?? []).map((l) => [l.lesson_id, l.subject_name]))
  const subjectOf = (lessonId: string) => subjects.get(lessonId) ?? null

  const toRows = (lessons: TodayLesson[], day: Day): Row[] =>
    lessons.map((item) => ({ item, day, subject: subjectOf(item.lesson.id) }))
  const allRows = [...toRows(today.lessons ?? [], 'today'), ...toRows(next?.lessons ?? [], 'next')]
  const subjectNames = [...new Set(allRows.map((row) => row.subject).filter((name): name is string => name !== null))]
  const visible = (rows: Row[]) => (subject ? rows.filter((row) => row.subject === subject) : rows)

  const todayRows = visible(toRows(today.lessons ?? [], 'today'))
  const nextRows = visible(toRows(next?.lessons ?? [], 'next'))

  return (
    <>
      <Backpack count={today.lessons?.length ?? null} builtAt={today.builtAt} />

      {/* Фільтри й групування за предметом мають сенс, лише коли назви предметів відомі. */}
      {subjectNames.length > 0 && (
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label={t.allSubjects}>
            {[null, ...subjectNames].map((name) => {
              const active = subject === name
              return (
                <button
                  key={name ?? 'all'}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setSubject(name)}
                  className={`${chipBase} ${active ? 'border-accent bg-surface-2 text-accent' : 'border-line text-muted hover:bg-surface'}`}
                >
                  {name ?? t.allSubjects}
                </button>
              )
            })}
          </div>
          <div className="flex shrink-0 rounded-xl border border-line bg-surface p-1" role="group">
            {(['days', 'subjects'] as const).map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={view === id}
                onClick={() => setView(id)}
                className={`h-9 rounded-lg px-4 text-sm leading-5 font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
                  view === id ? 'bg-surface-2 text-accent ring-1 ring-line-strong ring-inset' : 'text-muted'
                }`}
              >
                {t.view[id]}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
        <div className="flex min-w-0 flex-col gap-6">
          {view === 'days' || subjectNames.length === 0 ? (
            <>
              <RowGroup
                title={t.today(todayName)}
                rows={todayRows}
                local={local}
                progress={progress}
                empty={today.lessons ? t.empty : t.backpackMissingText}
              />
              {next && nextRows.length > 0 && (
                <RowGroup title={nextDayTitle(next.date)} rows={nextRows} local={local} progress={progress} />
              )}
            </>
          ) : (
            [...new Set(visible(allRows).map((row) => row.subject))].map((name) => (
              <RowGroup
                key={name ?? 'other'}
                title={name ?? t.otherSubject}
                rows={visible(allRows).filter((row) => row.subject === name)}
                local={local}
                progress={progress}
              />
            ))
          )}
        </div>
        <aside className="flex flex-col gap-6">
          <WindowTests tests={progress?.tests ?? []} subjectOf={subjectOf} />
          <Gaps />
        </aside>
      </div>
    </>
  )
}
