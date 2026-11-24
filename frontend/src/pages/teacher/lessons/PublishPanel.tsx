import type { LessonCheck, LessonOut } from '@/features/teacher/lessonEditorApi'
import { checkFallback, checkText, editor } from './content'
import { jumpTo } from './jump'
import { linkButton } from './styles'

const DEFAULT_LIMIT = 50 * 1024 * 1024

function mb(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toLocaleString('uk-UA', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} МБ`
}

/** Куди вести з перевірки: поле, модуль, картка, тест чи питання. */
function targetOf(lesson: LessonOut, c: LessonCheck): string | null {
  if (c.check === 'shelter_part') return 'field-shelter_part'
  if (c.check === 'modules') return 'part-shelter'
  if (c.check === 'lesson_size' || c.check === 'pack_day_size') return 'lesson-size'
  if (c.question_id) return `question-${c.question_id}`
  if (c.card_id) return `card-${c.card_id}`
  if (c.media_asset_id) {
    for (const m of lesson.modules) {
      const card = m.cards.find((x) => x.media_asset_id === c.media_asset_id)
      if (card) return `card-${card.id}`
    }
  }
  if (c.test_id) return `test-${c.test_id}`
  if (c.module_id) return `module-${c.module_id}`
  return null
}

/** Попередження, які видно й без сервера: відео без субтитрів, порожні картки й модулі. */
function localWarnings(lesson: LessonOut): LessonCheck[] {
  const out: LessonCheck[] = []
  for (const m of lesson.modules) {
    if (m.cards.length === 0) out.push({ check: 'empty_module', module_id: m.id })
    for (const c of m.cards) {
      if (c.kind === 'video' && c.media && !c.media.subtitles_id) out.push({ check: 'video_subtitles', card_id: c.id, media_asset_id: c.media.id })
      if (c.kind === 'text' && !String(c.body.text ?? '').trim()) out.push({ check: 'empty_card', card_id: c.id })
    }
  }
  return out
}

function CheckList({ lesson, title, items, tone }: { lesson: LessonOut; title: string; items: LessonCheck[]; tone: 'error' | 'warning' }) {
  if (items.length === 0) return null
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`flex flex-col gap-2 rounded-2xl border p-4 ${tone === 'error' ? 'border-accent/60 bg-accent-soft' : 'border-line bg-surface-2'}`}
    >
      <p className={`text-sm font-semibold ${tone === 'error' ? 'text-accent' : 'text-parchment'}`}>{title}</p>
      <ul className="flex flex-col gap-1">
        {items.map((c, i) => {
          const target = targetOf(lesson, c)
          return (
            <li key={`${c.check}-${i}`} className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
              <span className="min-w-0 flex-1">{checkText[c.check] ?? c.message ?? checkFallback}</span>
              {target && (
                <button type="button" onClick={() => jumpTo(target)} className={linkButton}>
                  {editor.checks.jump} →
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** Розмір уроку відносно ліміту, помилки публікації й попередження (з переходом до місця). */
export default function PublishPanel({ lesson, errors }: { lesson: LessonOut; errors: LessonCheck[] }) {
  const s = editor.size
  const limit = lesson.limit_bytes || DEFAULT_LIMIT
  const share = lesson.size_bytes / limit
  const color = share > 1 ? 'bg-danger' : share > 0.8 ? 'bg-accent' : 'bg-safe'
  // Сервер (коли навчиться) надсилає попередження сам; поки — рахуємо їх тут, без дублів.
  const blocking = new Set(errors.map((e) => `${e.check}:${e.card_id ?? e.media_asset_id ?? ''}`))
  const seen = new Set<string>()
  const warnings = [...(lesson.warnings ?? []), ...localWarnings(lesson)].filter((w) => {
    const key = `${w.check}:${w.card_id ?? w.media_asset_id ?? w.module_id ?? ''}`
    const alt = `${w.check}:${w.card_id ?? ''}`
    if (seen.has(key) || seen.has(alt) || blocking.has(key) || blocking.has(alt)) return false
    seen.add(key)
    if (w.card_id) seen.add(`${w.check}:${w.media_asset_id ?? ''}`)
    return true
  })

  return (
    <div className="flex flex-col gap-3">
      <div id="lesson-size" className="flex flex-col gap-1.5 rounded-[12px]">
        <div className="flex items-baseline justify-between gap-2 text-sm">
          <span className="text-muted">{s.label}</span>
          <span className="font-semibold text-parchment">{s.of(mb(lesson.size_bytes), mb(limit))}</span>
        </div>
        <div
          role="meter"
          aria-label={s.label}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-valuenow={lesson.size_bytes}
          className="h-2 overflow-hidden rounded-full bg-line-soft"
        >
          <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(1, share * 100))}%` }} />
        </div>
        {share > 1 ? (
          <p className="text-xs text-danger">{s.overLimit}</p>
        ) : share > 0.8 ? (
          <p className="text-xs text-accent">{s.nearLimit}</p>
        ) : null}
      </div>
      <CheckList lesson={lesson} title={editor.checks.errorsTitle} items={errors} tone="error" />
      {lesson.status === 'draft' && <CheckList lesson={lesson} title={editor.checks.warningsTitle} items={warnings} tone="warning" />}
    </div>
  )
}
