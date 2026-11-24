import { useRef, useState } from 'react'
import {
  errorMessage,
  nextPosition,
  useCreateTestMutation,
  useDeleteTestMutation,
  useReorderQuestionsMutation,
  useUpdateTestMutation,
} from '@/features/teacher/lessonEditorApi'
import type { LessonOut, TestOut, WindowHours } from '@/features/teacher/lessonEditorApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import FieldStatus from './FieldStatus'
import QuestionEditor from './QuestionEditor'
import { tracked } from './saveStatus'
import SortControls from './SortControls'
import { addButton, card, field, iconButton, inlineField, secondaryButton } from './styles'
import { useAutosave } from './useAutosave'
import { useSortable } from './useSortable'

const WINDOWS = [24, 48, 72] as const

function ErrorText({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <p role="alert" className="text-sm font-semibold text-accent">
      {error}
    </p>
  )
}

function TestItem({ lessonId, test, readOnly, fresh }: { lessonId: string; test: TestOut; readOnly: boolean; fresh: boolean }) {
  const t = editor.tests
  const [update] = useUpdateTestMutation()
  const [remove] = useDeleteTestMutation()
  const [reorder] = useReorderQuestionsMutation()
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  // Нові питання, ще не збережені на сервері (неповні): лише локально.
  // Щойно створений тест одразу з першим питанням: без зайвого натискання.
  const [drafts, setDrafts] = useState<string[]>(() => (fresh && test.questions.length === 0 ? [generateId()] : []))

  const title = useAutosave({
    draftKey: `test:${test.id}:title`,
    server: test.title,
    disabled: readOnly,
    isValid: (v) => v.trim() !== '',
    save: (value) => update({ lessonId, id: test.id, patch: { title: value.trim() } }).unwrap(),
  })
  const hours = useAutosave<WindowHours | null>({
    draftKey: `test:${test.id}:window`,
    server: test.window_enabled ? test.window_hours : null,
    disabled: readOnly,
    delay: 0,
    save: (value) => update({ lessonId, id: test.id, patch: { window_enabled: value !== null, window_hours: value } }).unwrap(),
  })

  const questions = [...test.questions].sort((a, b) => a.position - b.position)
  const saved = new Set(questions.map((q) => q.id))
  const pending = drafts.filter((id) => !saved.has(id))
  const sortable = useSortable(
    questions.map((q) => q.id),
    (ids) => {
      setError(null)
      tracked(`order:${test.id}`, () => reorder({ lessonId, testId: test.id, ids }).unwrap()).catch((err: unknown) =>
        setError(errorMessage(err)),
      )
    },
  )
  const byId = new Map(questions.map((q) => [q.id, q]))
  // Позиції чернеток: після збережених, кожна своя.
  const base = nextPosition(questions)

  const addQuestion = () => setDrafts((prev) => [...prev, generateId()])

  const del = async () => {
    if (test.questions.length > 0 && !window.confirm(t.confirmDelete(test.questions.length))) return
    setDeleting(true)
    try {
      await tracked(`test-del:${test.id}`, () => remove({ lessonId, id: test.id }).unwrap())
    } catch (err) {
      setError(errorMessage(err))
      setDeleting(false)
    }
  }

  const ids = [...sortable.order, ...pending]
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line-soft p-3 md:p-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          aria-label={t.name}
          value={title.value}
          disabled={readOnly}
          maxLength={200}
          onChange={(e) => title.set(e.target.value)}
          onBlur={title.flush}
          className={inlineField}
        />
        <select
          aria-label={t.window}
          value={hours.value ?? ''}
          disabled={readOnly}
          onChange={(e) => hours.set(e.target.value ? (Number(e.target.value) as WindowHours) : null)}
          className={`${field} h-10 text-sm`}
        >
          <option value="">{t.noWindow}</option>
          {WINDOWS.map((h) => (
            <option key={h} value={h}>
              {t.windowHours(h)}
            </option>
          ))}
        </select>
        {!readOnly && (
          <button type="button" aria-label={t.deleteTest} title={t.deleteTest} disabled={deleting} onClick={() => void del()} className={iconButton}>
            {deleting ? <Spinner /> : '✕'}
          </button>
        )}
      </div>
      <FieldStatus status={title.status} error={title.error} />
      <FieldStatus status={hours.status} error={hours.error} />
      <ErrorText error={error} />

      {ids.length === 0 ? (
        <p className="text-sm text-dim">{editor.questions.empty}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {ids.map((id, index) => {
            const question = byId.get(id) ?? null
            const sortIndex = sortable.order.indexOf(id)
            return (
              <li
                key={id}
                id={`question-${id}`}
                ref={question ? sortable.itemRef(id) : undefined}
                className={`rounded-[14px] ${sortable.dragging === id ? 'opacity-70 shadow-lg ring-2 ring-accent' : ''}`}
              >
                <QuestionEditor
                  lessonId={lessonId}
                  testId={test.id}
                  id={id}
                  question={question}
                  position={question ? question.position : base + pending.indexOf(id)}
                  number={index + 1}
                  readOnly={readOnly}
                  controls={
                    question ? (
                      <SortControls sortable={sortable} id={id} index={sortIndex} count={questions.length} disabled={readOnly} />
                    ) : undefined
                  }
                  onDeleted={() => setDrafts((prev) => prev.filter((x) => x !== id))}
                />
              </li>
            )
          })}
        </ol>
      )}
      {!readOnly && (
        <button type="button" onClick={addQuestion} className={`${addButton} self-start`}>
          + {editor.questions.add}
        </button>
      )}
    </div>
  )
}

export default function TestsSection({ lesson, readOnly }: { lesson: LessonOut; readOnly: boolean }) {
  const t = editor.tests
  const [create] = useCreateTestMutation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const idRef = useRef(generateId())
  const [fresh, setFresh] = useState<string | null>(null)

  const add = async () => {
    setBusy(true)
    setError(null)
    const id = idRef.current
    try {
      setFresh(id)
      await tracked(`test:${id}`, () =>
        create({ lessonId: lesson.id, id, title: t.defaultTitle, window_enabled: false, window_hours: null }).unwrap(),
      )
      idRef.current = generateId()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section id="tests" className={card}>
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.title}</h2>
        <p className="text-sm text-dim">{t.hint}</p>
      </div>
      {lesson.tests.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {lesson.tests.map((test) => (
            <li key={test.id} id={`test-${test.id}`} className="rounded-2xl">
              <TestItem lessonId={lesson.id} test={test} readOnly={readOnly} fresh={fresh === test.id} />
            </li>
          ))}
        </ul>
      )}
      <ErrorText error={error} />
      {!readOnly && (
        <button type="button" disabled={busy} onClick={() => void add()} className={`${secondaryButton} self-start`}>
          {busy && <Spinner />}+ {t.add}
        </button>
      )}
    </section>
  )
}
