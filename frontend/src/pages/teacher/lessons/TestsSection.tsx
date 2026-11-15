import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  nextPosition,
  useCreateQuestionMutation,
  useCreateTestMutation,
  useDeleteQuestionMutation,
  useDeleteTestMutation,
} from '@/features/teacher/lessonEditorApi'
import type { LessonOut, QuestionKind, QuestionOut, TestOut } from '@/features/teacher/lessonEditorApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import { card, dangerButton, field, primaryButton, secondaryButton } from './styles'
import { useAction } from './useAction'

const WINDOWS = [24, 48, 72] as const
const MAX_OPTIONS = 10

function ErrorText({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <p role="alert" className="text-sm font-semibold text-accent">
      {error}
    </p>
  )
}

function QuestionItem({ lessonId, question, readOnly }: { lessonId: string; question: QuestionOut; readOnly: boolean }) {
  const [remove] = useDeleteQuestionMutation()
  const del = useAction()
  const t = editor.questions
  return (
    <li className="flex flex-col gap-2 rounded-[14px] border border-line-soft p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-[15px] leading-[22.5px] text-parchment">
          {question.prompt}{' '}
          <span className="text-xs text-dim">
            · {question.kind === 'single' ? t.single : t.multiple} · {t.pointsLabel(question.points)}
          </span>
        </p>
        {!readOnly && (
          <button
            type="button"
            disabled={del.busy}
            onClick={() => void del.run(() => remove({ lessonId, id: question.id }).unwrap())}
            className={dangerButton}
          >
            {del.busy && <Spinner />}
            {t.deleteQuestion}
          </button>
        )}
      </div>
      <ul className="flex flex-col gap-1">
        {question.options.map((o) => {
          const correct = question.answer_key.includes(o.id)
          return (
            <li key={o.id} className={`text-sm ${correct ? 'font-semibold text-safe' : 'text-muted'}`}>
              {correct ? '✓ ' : '· '}
              {o.text}
            </li>
          )
        })}
      </ul>
      <ErrorText error={del.error} />
    </li>
  )
}

interface DraftOption {
  id: string
  text: string
  correct: boolean
}

/** id варіантів — короткі ключі (A, B, …): так їх і зберігає сервер (^[A-Za-z0-9_-]{1,16}$). */
function emptyOptions(): DraftOption[] {
  return [
    { id: 'A', text: '', correct: false },
    { id: 'B', text: '', correct: false },
  ]
}

function nextOptionId(options: DraftOption[]): string {
  const used = new Set(options.map((o) => o.id))
  for (let i = 0; i < 26; i++) {
    const id = String.fromCharCode(65 + i)
    if (!used.has(id)) return id
  }
  return `O${options.length}`
}

function AddQuestion({ lessonId, test }: { lessonId: string; test: TestOut }) {
  const t = editor.questions
  const [create] = useCreateQuestionMutation()
  const { busy, error, run } = useAction()
  const [prompt, setPrompt] = useState('')
  const [kind, setKind] = useState<QuestionKind>('single')
  const [points, setPoints] = useState(1)
  const [options, setOptions] = useState<DraftOption[]>(emptyOptions)
  const [id, setId] = useState(generateId)
  const [hint, setHint] = useState<string | null>(null)

  const setOption = (optionId: string, patch: Partial<DraftOption>) =>
    setOptions((prev) =>
      prev.map((o) => {
        if (o.id === optionId) return { ...o, ...patch }
        // «Одна правильна»: позначка іншого варіанта знімає попередню.
        if (patch.correct && kind === 'single') return { ...o, correct: false }
        return o
      }),
    )

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const filled = options.filter((o) => o.text.trim())
    const correct = filled.filter((o) => o.correct)
    if (filled.length < 2) return setHint(t.needOptions)
    if (correct.length === 0) return setHint(t.needCorrect)
    if (kind === 'single' && correct.length !== 1) return setHint(t.needOneCorrect)
    setHint(null)
    const ok = await run(() =>
      create({
        lessonId,
        testId: test.id,
        id,
        position: nextPosition(test.questions),
        kind,
        prompt: prompt.trim(),
        options: filled.map((o) => ({ id: o.id, text: o.text.trim() })),
        answer_key: correct.map((o) => o.id),
        points,
      }).unwrap(),
    )
    if (ok) {
      setPrompt('')
      setOptions(emptyOptions())
      setId(generateId())
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-3 rounded-[14px] border border-dashed border-line p-3">
      <label className="flex flex-col gap-1 text-sm text-muted">
        {t.prompt}
        <input required maxLength={2000} value={prompt} disabled={busy} onChange={(e) => setPrompt(e.target.value)} className={field} />
      </label>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.kind}
          <select
            value={kind}
            disabled={busy}
            onChange={(e) => {
              setKind(e.target.value as QuestionKind)
              setOptions((prev) => prev.map((o) => ({ ...o, correct: false })))
            }}
            className={field}
          >
            <option value="single">{t.single}</option>
            <option value="multiple">{t.multiple}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.points}
          <input
            type="number"
            min={1}
            max={100}
            value={points}
            disabled={busy}
            onChange={(e) => setPoints(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
            className={field}
          />
        </label>
      </div>
      <fieldset className="flex flex-col gap-2" disabled={busy}>
        {options.map((o, i) => (
          <div key={o.id} className="flex items-center gap-2">
            <input
              aria-label={t.option(i + 1)}
              placeholder={t.option(i + 1)}
              maxLength={1000}
              value={o.text}
              onChange={(e) => setOption(o.id, { text: e.target.value })}
              className={`${field} min-w-0 flex-1`}
            />
            <label className="flex shrink-0 items-center gap-2 text-sm text-muted">
              <input
                type={kind === 'single' ? 'radio' : 'checkbox'}
                name={`correct-${id}`}
                checked={o.correct}
                onChange={(e) => setOption(o.id, { correct: e.target.checked })}
                className="size-5 accent-[var(--color-accent)]"
              />
              {t.correct}
            </label>
            {options.length > 2 && (
              <button
                type="button"
                aria-label={t.removeOption}
                onClick={() => setOptions((prev) => prev.filter((x) => x.id !== o.id))}
                className={dangerButton}
              >
                ✕
              </button>
            )}
          </div>
        ))}
        {options.length < MAX_OPTIONS && (
          <button
            type="button"
            onClick={() => setOptions((prev) => [...prev, { id: nextOptionId(prev), text: '', correct: false }])}
            className="self-start rounded text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {t.addOption}
          </button>
        )}
      </fieldset>
      <ErrorText error={hint ?? error} />
      <button type="submit" disabled={busy || !prompt.trim()} className={`${secondaryButton} self-start`}>
        {busy && <Spinner />}
        {t.add}
      </button>
    </form>
  )
}

function TestItem({ lessonId, test, readOnly }: { lessonId: string; test: TestOut; readOnly: boolean }) {
  const t = editor.tests
  const [remove] = useDeleteTestMutation()
  const del = useAction()
  const questions = [...test.questions].sort((a, b) => a.position - b.position)
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line-soft p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">
          {test.title}{' '}
          <span className="text-xs font-normal text-dim">
            · {test.window_enabled && test.window_hours ? t.windowHours(test.window_hours) : t.noWindow}
          </span>
        </p>
        {!readOnly && (
          <button
            type="button"
            disabled={del.busy}
            onClick={() => void del.run(() => remove({ lessonId, id: test.id }).unwrap())}
            className={dangerButton}
          >
            {del.busy && <Spinner />}
            {t.deleteTest}
          </button>
        )}
      </div>
      <ErrorText error={del.error} />
      {questions.length === 0 ? (
        <p className="text-sm text-dim">{editor.questions.empty}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {questions.map((q) => (
            <QuestionItem key={q.id} lessonId={lessonId} question={q} readOnly={readOnly} />
          ))}
        </ul>
      )}
      {!readOnly && <AddQuestion lessonId={lessonId} test={test} />}
    </li>
  )
}

function AddTest({ lessonId }: { lessonId: string }) {
  const t = editor.tests
  const [create] = useCreateTestMutation()
  const { busy, error, run } = useAction()
  const [title, setTitle] = useState('')
  const [hours, setHours] = useState<24 | 48 | 72 | null>(null)
  const [id, setId] = useState(generateId)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const ok = await run(() =>
      create({ lessonId, id, title: title.trim(), window_enabled: hours !== null, window_hours: hours }).unwrap(),
    )
    if (ok) {
      setTitle('')
      setHours(null)
      setId(generateId())
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-2 md:flex-row md:items-end">
      <label className="flex flex-1 flex-col gap-1 text-sm text-muted">
        {t.name}
        <input
          required
          maxLength={200}
          placeholder={t.namePlaceholder}
          value={title}
          disabled={busy}
          onChange={(e) => setTitle(e.target.value)}
          className={field}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-muted md:w-56">
        {t.window}
        <select
          value={hours ?? ''}
          disabled={busy}
          onChange={(e) => setHours(e.target.value ? (Number(e.target.value) as 24 | 48 | 72) : null)}
          className={field}
        >
          <option value="">{t.noWindow}</option>
          {WINDOWS.map((h) => (
            <option key={h} value={h}>
              {t.windowHours(h)}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={busy || !title.trim()} className={primaryButton}>
        {busy && <Spinner />}
        {t.add}
      </button>
      <ErrorText error={error} />
    </form>
  )
}

export default function TestsSection({ lesson, readOnly }: { lesson: LessonOut; readOnly: boolean }) {
  const t = editor.tests
  return (
    <section className={card}>
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.title}</h2>
        <p className="text-sm text-dim">{t.hint}</p>
      </div>
      {lesson.tests.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {lesson.tests.map((test) => (
            <TestItem key={test.id} lessonId={lesson.id} test={test} readOnly={readOnly} />
          ))}
        </ul>
      )}
      {!readOnly && <AddTest lessonId={lesson.id} />}
    </section>
  )
}
