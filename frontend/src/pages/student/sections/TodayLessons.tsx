import { Link } from 'react-router'
import { useLiveQuery } from 'dexie-react-hooks'
import { useTodayPack } from '@/features/packs/usePacks'
import type { StudentLessonProgress, StudentTest } from '@/features/student/studentApi'
import { useStudentProgress } from '@/features/student/useStudentProgress'
import type { TodayLesson } from '@/features/packs/usePacks'
import { db } from '@/shared/db/db'
import type { LessonProgressRecord } from '@/shared/db/types'
import { todayLessons as t } from '../content'

type TestLine = { text: string; tone: 'ok' | 'warn' | 'dim' }

/** Що знає сервер про урок і його тести (прогрес учня, збережений і офлайн). */
interface ServerState {
  lessons: Map<string, StudentLessonProgress>
  tests: Map<string, StudentTest>
}

/**
 * Підсумок тесту уроку: оцінка сервера, локальний результат тренувального тесту або «не здано».
 * Тест у уроці зазвичай один; якщо їх кілька, показуємо перший як головний.
 */
function testLine(lesson: TodayLesson, byId: Map<string, LessonProgressRecord>, server: ServerState): TestLine {
  const first = lesson.lesson.tests[0]
  if (!first) return { text: t.test.none, tone: 'dim' }
  const record = byId.get(first.id)

  // Локального запису немає (здавали на іншому пристрої або до очищення): беремо прогрес сервера.
  if (!record) {
    const fromServer = server.tests.get(first.id)
    if (!fromServer || fromServer.attempts === 0 || fromServer.score === null) return { text: t.test.notTaken, tone: 'dim' }
    const score = t.test.score(fromServer.score)
    return fromServer.status === 'passed' ? { text: `${score} ✓`, tone: 'ok' } : { text: score, tone: 'warn' }
  }

  const result = record.server
  if (result) {
    if (result.credit_status === 'not_credited_late') return { text: t.test.late, tone: 'warn' }
    if (result.credit_status === 'not_credited_repeat') return { text: t.test.repeat, tone: 'dim' }
    if (result.score !== null) {
      // «Зараховано» ще не означає «складено»: поріг знає сервер (статус у прогресі учня).
      const passed = server.tests.get(first.id)?.status !== 'not_passed'
      const score = t.test.score(result.score)
      return passed ? { text: `${score} ✓`, tone: 'ok' } : { text: score, tone: 'warn' }
    }
  }
  if (record.score) return { text: t.test.local(record.score.points, record.score.max), tone: 'ok' }
  return { text: t.test.waiting, tone: 'dim' }
}

const toneStyle = { ok: 'text-safe', warn: 'text-accent', dim: 'text-dim' }

function LessonCard({
  item,
  byId,
  server,
}: {
  item: TodayLesson
  byId: Map<string, LessonProgressRecord>
  server: ServerState
}) {
  const modules = item.lesson.modules
  // Пройдено — за локальним прогресом (ще не синхронізованим) або за сервером, як і на маршруті.
  const fromServer = server.lessons.get(item.lesson.id)
  const localModules = modules.filter((m) => byId.has(m.id)).length
  const modulesDone =
    (fromServer?.progress_pct ?? 0) >= 100
      ? modules.length
      : Math.min(modules.length, Math.max(localModules, fromServer?.modules_done ?? 0))
  const testsDone = item.lesson.tests.every((test) => byId.has(test.id) || (server.tests.get(test.id)?.attempts ?? 0) > 0)
  const allDone = modulesDone === modules.length && testsDone
  const started = modulesDone > 0 || item.lesson.tests.some((test) => byId.has(test.id))
  const pct = modules.length === 0 ? 0 : Math.round((modulesDone / modules.length) * 100)
  const test = testLine(item, byId, server)
  const isNow = item.status === 'now'

  return (
    <li
      className={`flex flex-col gap-3 rounded-2xl border p-4 ${
        isNow ? 'border-accent/50 bg-surface-2' : 'border-line bg-surface-2/50'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-dim">
          {item.startsAt}–{item.endsAt} · {t.minutes(item.minutes)}
        </span>
        {isNow && (
          <span className="rounded-md bg-accent px-2 py-0.5 text-[11px] leading-[16.5px] font-semibold text-oil">
            {t.now}
          </span>
        )}
      </div>
      <h3 className="text-[17px] leading-[24px] font-semibold text-parchment">{item.lesson.title}</h3>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-dim">{t.modulesLabel}</span>
          <span className={allDone ? 'font-semibold text-safe' : 'text-muted'}>
            {t.modules(modulesDone, modules.length)}
          </span>
        </div>
        <span
          className="block h-2 rounded-full bg-line-soft"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label={t.modulesLabel}
        >
          <span
            className={`block h-2 rounded-full ${pct >= 100 ? 'bg-safe' : 'bg-accent'}`}
            style={{ width: `${pct}%` }}
          />
        </span>
      </div>

      <p className="flex items-center justify-between text-xs">
        <span className="text-dim">{t.test.label}</span>
        <span className={`font-semibold ${toneStyle[test.tone]}`}>{test.text}</span>
      </p>

      <Link
        to={`/student/lesson?lesson=${item.lesson.id}`}
        className={`mt-auto flex h-11 items-center justify-center rounded-[10px] text-sm font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
          allDone
            ? 'border border-line-strong text-parchment hover:bg-surface'
            : 'bg-accent text-oil focus-visible:ring-parchment/60'
        }`}
      >
        {allDone ? t.review : started ? t.continue : t.start}
      </Link>
    </li>
  )
}

/**
 * Уроки на сьогодні картками: прогрес модулів, результат тесту, кнопка «Почати / Продовжити /
 * Переглянути». Усе з пристрою (пакет і локальний прогрес), тож працює без мережі.
 */
export default function TodayLessons() {
  const { lessons } = useTodayPack()
  const records = useLiveQuery(() => db.progress.toArray(), [])
  const { progress } = useStudentProgress()
  const byId = new Map((records ?? []).map((r) => [r.id, r]))
  const server: ServerState = {
    lessons: new Map((progress?.lessons ?? []).map((l) => [l.lesson_id, l])),
    tests: new Map((progress?.tests ?? []).map((test) => [test.test_id, test])),
  }

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{t.title}</h2>
        <p className="max-w-[102px] text-right text-xs text-dim md:max-w-none">
          {lessons ? t.hintSaved : t.hintMissing}
        </p>
      </div>
      {(!lessons || lessons.length === 0) && (
        <p role="status" className="text-sm text-muted">
          {lessons ? t.empty : t.noPack}
        </p>
      )}
      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(lessons ?? []).map((item) => (
          <LessonCard key={item.key} item={item} byId={byId} server={server} />
        ))}
      </ul>
    </section>
  )
}
