import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  nextPosition,
  useCreateCardMutation,
  useCreateModuleMutation,
  useDeleteCardMutation,
  useDeleteModuleMutation,
  useUpdateCardMutation,
} from '@/features/teacher/lessonEditorApi'
import type { CardOut, LessonOut, ModuleOut, ModulePart } from '@/features/teacher/lessonEditorApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import { card, dangerButton, field, primaryButton, secondaryButton, textarea } from './styles'
import { useAction } from './useAction'

function cardText(c: CardOut): string {
  return typeof c.body.text === 'string' ? c.body.text : ''
}

function ErrorText({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <p role="alert" className="text-sm font-semibold text-accent">
      {error}
    </p>
  )
}

/** Текстова картка: редагується на місці, зберігається кнопкою, коли текст змінено. */
function CardEditor({ lessonId, item, readOnly }: { lessonId: string; item: CardOut; readOnly: boolean }) {
  const [update] = useUpdateCardMutation()
  const [remove] = useDeleteCardMutation()
  const save = useAction()
  const del = useAction()
  const [text, setText] = useState(() => cardText(item))
  const saved = cardText(item)
  const dirty = text.trim() !== saved

  if (item.kind !== 'text') {
    return <p className="rounded-[10px] border border-line-soft p-3 text-sm text-dim">{editor.cards.nonText}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      <textarea
        aria-label={editor.cards.placeholder}
        value={text}
        disabled={readOnly || save.busy}
        onChange={(e) => setText(e.target.value)}
        className={textarea}
      />
      {!readOnly && (
        <div className="flex flex-wrap gap-2">
          {dirty && (
            <button
              type="button"
              disabled={save.busy || !text.trim()}
              onClick={() => void save.run(() => update({ lessonId, id: item.id, text: text.trim() }).unwrap())}
              className={secondaryButton}
            >
              {save.busy && <Spinner />}
              {save.busy ? editor.saving : editor.save}
            </button>
          )}
          <button
            type="button"
            disabled={del.busy}
            onClick={() => void del.run(() => remove({ lessonId, id: item.id }).unwrap())}
            className={dangerButton}
          >
            {del.busy && <Spinner />}
            {editor.delete}
          </button>
        </div>
      )}
      <ErrorText error={save.error ?? del.error} />
    </div>
  )
}

function AddCard({ lessonId, module }: { lessonId: string; module: ModuleOut }) {
  const [create] = useCreateCardMutation()
  const { busy, error, run } = useAction()
  const [text, setText] = useState('')
  // id нової картки фіксуємо до успіху: повтор після обриву мережі не створить дубля.
  const [id, setId] = useState(generateId)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const ok = await run(() =>
      create({ lessonId, moduleId: module.id, id, position: nextPosition(module.cards), text: text.trim() }).unwrap(),
    )
    if (ok) {
      setText('')
      setId(generateId())
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-2">
      <textarea
        aria-label={editor.cards.add}
        placeholder={editor.cards.placeholder}
        value={text}
        disabled={busy}
        onChange={(e) => setText(e.target.value)}
        className={textarea}
      />
      <button type="submit" disabled={busy || !text.trim()} className={`${secondaryButton} self-start`}>
        {busy && <Spinner />}
        {editor.cards.add}
      </button>
      <ErrorText error={error} />
    </form>
  )
}

function ModuleItem({ lessonId, module, readOnly }: { lessonId: string; module: ModuleOut; readOnly: boolean }) {
  const [remove] = useDeleteModuleMutation()
  const del = useAction()
  const cards = [...module.cards].sort((a, b) => a.position - b.position)

  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line-soft p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">
          {module.title} <span className="text-xs font-normal text-dim">· {editor.modules.minutesLabel(module.duration_min)}</span>
        </p>
        {!readOnly && (
          <button
            type="button"
            disabled={del.busy}
            onClick={() => void del.run(() => remove({ lessonId, id: module.id }).unwrap())}
            className={dangerButton}
          >
            {del.busy && <Spinner />}
            {editor.modules.deleteModule}
          </button>
        )}
      </div>
      <ErrorText error={del.error} />
      {cards.length === 0 && <p className="text-sm text-dim">{editor.cards.empty}</p>}
      {cards.map((c) => (
        // key з текстом: після збереження на сервері поле підхоплює нове значення.
        <CardEditor key={`${c.id}-${cardText(c)}`} lessonId={lessonId} item={c} readOnly={readOnly} />
      ))}
      {!readOnly && <AddCard lessonId={lessonId} module={module} />}
    </li>
  )
}

function AddModule({ lessonId, part, modules }: { lessonId: string; part: ModulePart; modules: ModuleOut[] }) {
  const [create] = useCreateModuleMutation()
  const { busy, error, run } = useAction()
  const [title, setTitle] = useState('')
  const [minutes, setMinutes] = useState(3)
  const [id, setId] = useState(generateId)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const ok = await run(() =>
      create({ lessonId, id, part, position: nextPosition(modules), title: title.trim(), duration_min: minutes }).unwrap(),
    )
    if (ok) {
      setTitle('')
      setId(generateId())
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-2 md:flex-row md:items-end">
      <label className="flex flex-1 flex-col gap-1 text-sm text-muted">
        {editor.modules.name}
        <input required maxLength={200} value={title} disabled={busy} onChange={(e) => setTitle(e.target.value)} className={field} />
      </label>
      <label className="flex flex-col gap-1 text-sm text-muted md:w-28">
        {editor.modules.minutes}
        <input
          type="number"
          min={1}
          max={10}
          required
          value={minutes}
          disabled={busy}
          onChange={(e) => setMinutes(Math.min(10, Math.max(1, Number(e.target.value) || 1)))}
          className={field}
        />
      </label>
      <button type="submit" disabled={busy || !title.trim()} className={primaryButton}>
        {busy && <Spinner />}
        {editor.modules.add}
      </button>
      <ErrorText error={error} />
    </form>
  )
}

/** Модулі однієї частини уроку (укриття або основна) з картками. */
export default function ModulesSection({ lesson, part, readOnly }: { lesson: LessonOut; part: ModulePart; readOnly: boolean }) {
  const modules = lesson.modules.filter((m) => m.part === part).sort((a, b) => a.position - b.position)
  const t = editor.modules
  return (
    <section className={card}>
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{part === 'shelter' ? t.shelter : t.main}</h2>
        <p className="text-sm text-dim">{part === 'shelter' ? t.shelterHint : t.mainHint}</p>
      </div>
      {modules.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {modules.map((m) => (
            <ModuleItem key={m.id} lessonId={lesson.id} module={m} readOnly={readOnly} />
          ))}
        </ul>
      )}
      {!readOnly && <AddModule lessonId={lesson.id} part={part} modules={modules} />}
    </section>
  )
}
