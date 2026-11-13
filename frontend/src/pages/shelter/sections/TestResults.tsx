import type { LessonStep } from '@/features/lessons/lessonSteps'
import type { LessonProgressRecord } from '@/shared/db/types'
import { results } from '../content'

type Line = { value: string; note: string; tone: 'ok' | 'warn' | 'dim' }

function lineFor(record: LessonProgressRecord | undefined): Line {
  if (!record) return { value: '—', note: results.notTaken, tone: 'dim' }
  const server = record.server
  // Оцінка сервера головна: вона враховує вікно тесту й першу спробу.
  if (server) {
    if (server.credit_status === 'not_credited_late') return { value: server.score !== null ? results.server(server.score) : '—', note: results.late, tone: 'warn' }
    if (server.credit_status === 'not_credited_repeat') return { value: server.score !== null ? results.server(server.score) : '—', note: results.repeat, tone: 'dim' }
    if (server.score === null) return { value: '—', note: results.checking, tone: 'dim' }
    return { value: results.server(server.score), note: results.credited, tone: 'ok' }
  }
  // Тренувальний тест перевірено на пристрої; оцінюваний чекає синхронізації.
  if (record.score) return { value: results.local(record.score.points, record.score.max), note: results.pending, tone: 'dim' }
  return { value: '—', note: results.pending, tone: 'dim' }
}

const toneStyle = { ok: 'text-safe', warn: 'text-accent', dim: 'text-dim' }

/** Оцінки за тести уроку: локальна (тренувальний тест) або від сервера після синхронізації. */
export default function TestResults({ steps, records }: { steps: LessonStep[]; records: LessonProgressRecord[] }) {
  const tests = steps.filter((step) => step.kind === 'test')
  if (tests.length === 0) return null
  const byId = new Map(records.map((record) => [record.id, record]))

  return (
    <div className="flex flex-col gap-2 border-t border-line-soft pt-4">
      <h3 className="text-sm font-semibold text-muted">{results.title}</h3>
      <ul className="flex flex-col gap-2">
        {tests.map((step) => {
          const line = lineFor(byId.get(step.id))
          return (
            <li key={step.id} className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 flex-1 text-[15px] leading-[22.5px] text-parchment">{step.title}</span>
              <span className="shrink-0 text-right">
                <span className="block text-[15px] font-semibold text-parchment">{line.value}</span>
                <span className={`block text-xs ${toneStyle[line.tone]}`}>{line.note}</span>
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
