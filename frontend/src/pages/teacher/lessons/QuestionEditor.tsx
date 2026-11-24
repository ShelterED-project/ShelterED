import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { errorMessage, useCreateQuestionMutation, useDeleteQuestionMutation, useUpdateQuestionMutation } from '@/features/teacher/lessonEditorApi'
import type { QuestionKind, QuestionOption, QuestionOut } from '@/features/teacher/lessonEditorApi'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import FieldStatus from './FieldStatus'
import { fromServer, missing, newQuestion, nextId, sameWire, switchKind, toWire } from './questionModel'
import type { EditorQuestion } from './questionModel'
import { tracked } from './saveStatus'
import { field, iconButton, linkButton, textarea } from './styles'
import { useAutosave } from './useAutosave'

const t = editor.questions
const KINDS: QuestionKind[] = ['single', 'multiple', 'text', 'match']
const MAX_OPTIONS = 10

/** Фокус на щойно доданому полі (новий варіант, пара). */
function focusLast(container: HTMLElement | null, selector: string) {
  requestAnimationFrame(() => {
    const all = container?.querySelectorAll<HTMLInputElement>(selector)
    all?.[all.length - 1]?.focus()
  })
}

function ChoiceEditor({ q, set, disabled }: { q: EditorQuestion; set: (q: EditorQuestion) => void; disabled: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  const single = q.kind === 'single'
  const setOption = (id: string, text: string) => set({ ...q, options: q.options.map((o) => (o.id === id ? { ...o, text } : o)) })
  const toggle = (id: string) =>
    set({ ...q, correct: single ? [id] : q.correct.includes(id) ? q.correct.filter((x) => x !== id) : [...q.correct, id] })
  const add = () => {
    if (q.options.length >= MAX_OPTIONS) return
    set({ ...q, options: [...q.options, { id: nextId('', q.options.map((o) => o.id)), text: '' }] })
    focusLast(box.current, 'input[data-option]')
  }
  // Enter в останньому варіанті — новий варіант.
  const onKey = (e: KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (index === q.options.length - 1) add()
      else box.current?.querySelectorAll<HTMLInputElement>('input[data-option]')[index + 1]?.focus()
    }
  }

  return (
    <div ref={box} className="flex flex-col gap-2">
      {q.options.map((o, i) => {
        const correct = q.correct.includes(o.id)
        return (
          <div key={o.id} className="flex items-center gap-2">
            <button
              type="button"
              role={single ? 'radio' : 'checkbox'}
              aria-checked={correct}
              aria-label={`${t.markCorrect}: ${t.option(i + 1)}`}
              title={t.markCorrect}
              disabled={disabled}
              onClick={() => toggle(o.id)}
              className={`flex size-11 shrink-0 items-center justify-center border-2 text-lg font-bold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
                single ? 'rounded-full' : 'rounded-[10px]'
              } ${correct ? 'border-safe bg-safe/20 text-safe' : 'border-line-strong text-transparent hover:border-safe/60'}`}
            >
              ✓
            </button>
            <input
              data-option
              aria-label={t.option(i + 1)}
              placeholder={t.option(i + 1)}
              maxLength={1000}
              value={o.text}
              disabled={disabled}
              onChange={(e) => setOption(o.id, e.target.value)}
              onKeyDown={(e) => onKey(e, i)}
              className={`${field} min-w-0 flex-1 ${correct ? 'border-safe/60' : ''}`}
            />
            {q.options.length > 2 && !disabled && (
              <button
                type="button"
                aria-label={t.removeOption}
                title={t.removeOption}
                onClick={() => set({ ...q, options: q.options.filter((x) => x.id !== o.id), correct: q.correct.filter((x) => x !== o.id) })}
                className={iconButton}
              >
                ✕
              </button>
            )}
          </div>
        )
      })}
      {q.options.length < MAX_OPTIONS && !disabled && (
        <button type="button" onClick={add} className={linkButton}>
          {t.addOption}
        </button>
      )}
    </div>
  )
}

function TextAnswersEditor({ q, set, disabled }: { q: EditorQuestion; set: (q: EditorQuestion) => void; disabled: boolean }) {
  const [input, setInput] = useState('')
  const commit = () => {
    const value = input.trim()
    if (!value || q.accepted.length >= 20) return
    if (!q.accepted.some((a) => a.toLowerCase() === value.toLowerCase())) set({ ...q, accepted: [...q.accepted, value] })
    setInput('')
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted">{t.accepted}</p>
      {q.accepted.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {q.accepted.map((a) => (
            <li key={a} className="flex items-center gap-1 rounded-full border border-safe/50 bg-safe/10 py-1 pr-1 pl-3 text-[15px] text-parchment">
              {a}
              {!disabled && (
                <button
                  type="button"
                  aria-label={t.removeAnswer(a)}
                  onClick={() => set({ ...q, accepted: q.accepted.filter((x) => x !== a) })}
                  className="flex size-8 items-center justify-center rounded-full text-muted hover:bg-surface-2 hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
                >
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {!disabled && (
        <input
          aria-label={t.accepted}
          placeholder={t.acceptedPlaceholder}
          maxLength={200}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ',') {
              e.preventDefault()
              commit()
            }
          }}
          onBlur={commit}
          className={field}
        />
      )}
      <p className="text-xs text-dim">{t.acceptedHint}</p>
    </div>
  )
}

function MatchEditor({ q, set, disabled }: { q: EditorQuestion; set: (q: EditorQuestion) => void; disabled: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  const rightIds = () => [...q.pairs.map((p) => p.right.id), ...q.extras.map((x) => x.id)]
  const setPair = (index: number, side: 'left' | 'right', text: string) =>
    set({ ...q, pairs: q.pairs.map((p, i) => (i === index ? { ...p, [side]: { ...p[side], text } } : p)) })
  const addPair = () => {
    if (q.pairs.length >= MAX_OPTIONS) return
    set({
      ...q,
      pairs: [...q.pairs, { left: { id: nextId('L', q.pairs.map((p) => p.left.id)), text: '' }, right: { id: nextId('R', rightIds()), text: '' } }],
    })
    focusLast(box.current, 'input[data-left]')
  }
  const setExtra = (id: string, text: string) => set({ ...q, extras: q.extras.map((x) => (x.id === id ? { ...x, text } : x)) })

  return (
    <div ref={box} className="flex flex-col gap-3">
      <p className="text-sm text-muted">{t.pairs}</p>
      {q.pairs.map((p, i) => (
        <div key={p.left.id} className="flex items-center gap-2">
          <input
            data-left
            aria-label={t.left(i + 1)}
            placeholder={t.left(i + 1)}
            maxLength={1000}
            value={p.left.text}
            disabled={disabled}
            onChange={(e) => setPair(i, 'left', e.target.value)}
            className={`${field} min-w-0 flex-1`}
          />
          <span aria-hidden="true" className="text-accent">
            →
          </span>
          <input
            aria-label={t.right(i + 1)}
            placeholder={t.right(i + 1)}
            maxLength={1000}
            value={p.right.text}
            disabled={disabled}
            onChange={(e) => setPair(i, 'right', e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && i === q.pairs.length - 1) {
                e.preventDefault()
                addPair()
              }
            }}
            className={`${field} min-w-0 flex-1`}
          />
          {q.pairs.length > 2 && !disabled && (
            <button type="button" aria-label={t.removePair} title={t.removePair} onClick={() => set({ ...q, pairs: q.pairs.filter((_, j) => j !== i) })} className={iconButton}>
              ✕
            </button>
          )}
        </div>
      ))}
      {q.pairs.length < MAX_OPTIONS && !disabled && (
        <button type="button" onClick={addPair} className={linkButton}>
          {t.addPair}
        </button>
      )}
      <div className="flex flex-col gap-2 border-t border-line-soft pt-3">
        <p className="text-sm text-muted">
          {t.extras} <span className="text-xs text-dim">— {t.extrasHint}</span>
        </p>
        {q.extras.map((x, i) => (
          <div key={x.id} className="flex items-center gap-2">
            <input
              aria-label={t.extra(i + 1)}
              placeholder={t.extra(i + 1)}
              maxLength={1000}
              value={x.text}
              disabled={disabled}
              onChange={(e) => setExtra(x.id, e.target.value)}
              className={`${field} min-w-0 flex-1`}
            />
            {!disabled && (
              <button type="button" aria-label={t.removeOption} onClick={() => set({ ...q, extras: q.extras.filter((e) => e.id !== x.id) })} className={iconButton}>
                ✕
              </button>
            )}
          </div>
        ))}
        {q.pairs.length + q.extras.length < MAX_OPTIONS && !disabled && (
          <button type="button" onClick={() => set({ ...q, extras: [...q.extras, { id: nextId('R', rightIds()), text: '' }] })} className={linkButton}>
            {t.addExtra}
          </button>
        )}
      </div>
    </div>
  )
}

function summary(q: EditorQuestion): string {
  if (q.kind === 'text') return q.accepted.join(' / ')
  if (q.kind === 'match') return q.pairs.filter((p) => p.left.text && p.right.text).map((p) => `${p.left.text} → ${p.right.text}`).join(' · ')
  return q.options.filter((o) => q.correct.includes(o.id)).map((o: QuestionOption) => `✓ ${o.text}`).join(' · ')
}

/**
 * Питання тесту: усі чотири види, автозбереження. Нове питання — локальна чернетка, поки не
 * заповнене (сервер приймає лише повне); тоді створюється з id, зафіксованим наперед.
 */
export default function QuestionEditor({
  lessonId,
  testId,
  id,
  question,
  position,
  number,
  readOnly,
  controls,
  onDeleted,
}: {
  lessonId: string
  testId: string
  id: string
  /** Збережене питання; немає — нова чернетка */
  question: QuestionOut | null
  position: number
  number: number
  readOnly: boolean
  controls?: ReactNode
  onDeleted: () => void
}) {
  const [create] = useCreateQuestionMutation()
  const [update] = useUpdateQuestionMutation()
  const [remove] = useDeleteQuestionMutation()
  const createdRef = useRef(question !== null)
  const [open, setOpen] = useState(question === null)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const promptRef = useRef<HTMLTextAreaElement>(null)
  const [initial] = useState(newQuestion)

  const draft = useAutosave<EditorQuestion>({
    draftKey: `question:${id}`,
    server: question ? fromServer(question) : initial,
    disabled: readOnly,
    same: sameWire,
    isValid: (q) => missing(q) === null,
    save: async (q) => {
      const wire = toWire(q)
      if (createdRef.current || question) {
        await update({ lessonId, id, ...wire }).unwrap()
      } else {
        await create({ lessonId, testId, id, position, ...wire }).unwrap()
        createdRef.current = true
      }
    },
  })
  const q = draft.value
  const hint = missing(q)

  // Нове питання — одразу курсор у тексті питання.
  const isNew = question === null
  useEffect(() => {
    if (isNew) promptRef.current?.focus()
    // Лише при появі: далі фокус не перехоплюємо.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const del = async () => {
    if (!createdRef.current && !question) return onDeleted()
    setDeleting(true)
    try {
      await tracked(`q-del:${id}`, () => remove({ lessonId, id }).unwrap())
      onDeleted()
    } catch (err) {
      setError(errorMessage(err))
      setDeleting(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-[14px] border border-line-soft bg-surface p-3">
      <div className="flex items-start gap-1">
        {controls}
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="flex min-h-10 min-w-0 flex-1 flex-col items-start rounded-[10px] px-2 py-1 text-left hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <span className="text-xs text-dim">
            {t.number(number)} · {t.kinds[q.kind]} · {t.pointsLabel(q.points)}
          </span>
          <span className="text-[15px] leading-[22.5px] font-semibold text-parchment">{q.prompt || '…'}</span>
          {!open && summary(q) && <span className="text-sm text-safe">{summary(q)}</span>}
        </button>
        {!readOnly && (
          <button type="button" aria-label={t.deleteQuestion} title={t.deleteQuestion} disabled={deleting} onClick={() => void del()} className={iconButton}>
            {deleting ? <Spinner /> : '✕'}
          </button>
        )}
      </div>

      {open && (
        <fieldset disabled={readOnly} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm text-muted">
            {t.prompt}
            <textarea
              ref={promptRef}
              rows={2}
              maxLength={2000}
              placeholder={t.promptPlaceholder}
              value={q.prompt}
              onChange={(e) => draft.set({ ...q, prompt: e.target.value })}
              onBlur={draft.flush}
              className={`${textarea} min-h-16`}
            />
          </label>

          <div role="radiogroup" aria-label={t.kind} className="grid grid-cols-2 gap-1 rounded-[12px] bg-oil/50 p-1 md:grid-cols-4">
            {KINDS.map((kind) => (
              <button
                key={kind}
                type="button"
                role="radio"
                aria-checked={q.kind === kind}
                onClick={() => draft.set(switchKind(q, kind))}
                className={`min-h-10 rounded-[10px] px-2 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
                  q.kind === kind ? 'bg-accent text-oil' : 'text-muted hover:bg-surface-2 hover:text-parchment'
                }`}
              >
                {t.kinds[kind]}
              </button>
            ))}
          </div>

          {q.kind === 'text' ? (
            <TextAnswersEditor q={q} set={draft.set} disabled={readOnly} />
          ) : q.kind === 'match' ? (
            <MatchEditor q={q} set={draft.set} disabled={readOnly} />
          ) : (
            <ChoiceEditor q={q} set={draft.set} disabled={readOnly} />
          )}

          <label className="flex flex-col gap-1 text-sm text-muted">
            {t.explanation}
            <span className="text-xs text-dim">{t.explanationHint}</span>
            <textarea
              rows={2}
              maxLength={2000}
              placeholder={t.explanationPlaceholder}
              value={q.explanation}
              onChange={(e) => draft.set({ ...q, explanation: e.target.value })}
              onBlur={draft.flush}
              className={`${textarea} min-h-16`}
            />
          </label>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-muted">
              {t.points}
              <input
                type="number"
                min={1}
                max={100}
                value={q.points}
                onChange={(e) => draft.set({ ...q, points: Math.min(100, Math.max(1, Number(e.target.value) || 1)) })}
                className={`${field} w-20`}
              />
            </label>
            <button type="button" onClick={() => setOpen(false)} className={linkButton}>
              {t.collapse}
            </button>
          </div>
        </fieldset>
      )}
      {!readOnly && hint && (q.prompt || question || draft.status === 'invalid') && (
        <p className="text-sm text-accent">
          {t.draft} {hint}
        </p>
      )}
      <FieldStatus status={draft.status} error={draft.error ?? error} />
      {error && draft.status !== 'error' && (
        <p role="alert" className="text-sm font-semibold text-accent">
          {error}
        </p>
      )}
    </div>
  )
}
