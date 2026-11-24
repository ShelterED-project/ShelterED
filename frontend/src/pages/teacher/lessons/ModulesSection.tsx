import { useEffect, useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'
import {
  errorMessage,
  nextPosition,
  useCreateModuleMutation,
  useDeleteModuleMutation,
  useReorderCardsMutation,
  useReorderModulesMutation,
  useUpdateModuleMutation,
} from '@/features/teacher/lessonEditorApi'
import type { LessonOut, ModuleOut, ModulePart } from '@/features/teacher/lessonEditorApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import CardItem from './CardItem'
import { editor } from './content'
import FieldStatus from './FieldStatus'
import PendingMark from './PendingMark'
import { focusOnMount, takeFocus } from './jump'
import { tracked } from './saveStatus'
import SortControls from './SortControls'
import { addButton, card, field, iconButton, inlineField, linkButton, primaryButton, secondaryButton } from './styles'
import { isCommonsUrl, useModuleImport } from './useModuleImport'
import type { ImportItem } from './useModuleImport'
import { useAutosave } from './useAutosave'
import { useSortable } from './useSortable'

const MINUTES = Array.from({ length: 10 }, (_, i) => i + 1)

function ErrorText({ error }: { error: string | null }) {
  if (!error) return null
  return (
    <p role="alert" className="text-sm font-semibold text-accent">
      {error}
    </p>
  )
}

function ImportRow({ item, onDismiss }: { item: ImportItem; onDismiss: () => void }) {
  const m = editor.media
  return (
    <li className="flex flex-col gap-2 rounded-[14px] border border-dashed border-line-strong bg-surface-2 p-3">
      <div className="flex items-center gap-2">
        {!item.error && !item.note && <Spinner className="text-accent" />}
        <p className="min-w-0 flex-1 truncate text-sm font-semibold text-parchment">{item.label}</p>
        {(item.error || item.note) && (
          <button type="button" onClick={onDismiss} className={linkButton}>
            {m.dismiss}
          </button>
        )}
      </div>
      {item.status && !item.error && <p className="text-sm text-muted">{item.status}</p>}
      {item.progress !== null && !item.error && (
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(item.progress * 100)}
          className="h-1.5 overflow-hidden rounded-full bg-line-soft"
        >
          <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(item.progress * 100)}%` }} />
        </div>
      )}
      {item.note && <p className="text-sm text-safe">{item.note}</p>}
      {item.error && (
        <div className="flex flex-wrap items-center gap-2">
          <p role="alert" className="flex-1 text-sm font-semibold text-accent">
            {item.error}
          </p>
          {item.retry && (
            <button type="button" onClick={item.retry} className={secondaryButton}>
              {m.retry}
            </button>
          )}
        </div>
      )}
    </li>
  )
}

/** Рядок «Додати»: текст, файли, PDF, Wikimedia Commons. */
function AddBar({ onText, onFiles, onCommons }: { onText: () => void; onFiles: (files: File[]) => void; onCommons: (url: string) => void }) {
  const c = editor.cards
  const m = editor.media
  const [commons, setCommons] = useState(false)
  const [url, setUrl] = useState('')
  const [urlError, setUrlError] = useState<string | null>(null)
  const files = useRef<HTMLInputElement>(null)
  const pdf = useRef<HTMLInputElement>(null)

  const submitUrl = (value: string) => {
    if (!isCommonsUrl(value)) {
      setUrlError(m.commonsBadUrl)
      return
    }
    onCommons(value)
    setUrl('')
    setUrlError(null)
    setCommons(false)
  }

  const picked = (input: HTMLInputElement | null) => {
    if (!input?.files) return
    onFiles([...input.files])
    input.value = ''
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onText} className={addButton}>
          + {c.addText}
        </button>
        <button type="button" onClick={() => files.current?.click()} className={addButton}>
          + {c.addMedia}
        </button>
        <button type="button" onClick={() => pdf.current?.click()} title={c.pdfHint} className={addButton}>
          + {c.addPdf}
        </button>
        <button type="button" aria-expanded={commons} onClick={() => setCommons((v) => !v)} className={addButton}>
          + {c.addCommons}
        </button>
        <input ref={files} type="file" multiple accept="image/*,video/*" onChange={(e) => picked(e.currentTarget)} className="sr-only" tabIndex={-1} />
        <input ref={pdf} type="file" accept="application/pdf,.pdf" onChange={(e) => picked(e.currentTarget)} className="sr-only" tabIndex={-1} />
      </div>
      <p className="text-xs text-dim">{c.pdfHint}</p>
      {commons && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submitUrl(url)
          }}
          className="flex flex-col gap-1"
        >
          <label className="flex flex-col gap-1 text-sm text-muted">
            {m.commonsLabel}
            <div className="flex gap-2">
              <input
                autoFocus
                type="url"
                inputMode="url"
                value={url}
                placeholder={m.commonsPlaceholder}
                onChange={(e) => setUrl(e.target.value)}
                // Вставили посилання — одразу додаємо, без зайвого натискання.
                onPaste={(e) => {
                  const pasted = e.clipboardData.getData('text')
                  if (isCommonsUrl(pasted)) {
                    e.preventDefault()
                    submitUrl(pasted)
                  }
                }}
                className={`${field} min-w-0 flex-1`}
              />
              <button type="submit" disabled={!url.trim()} className={primaryButton}>
                {m.commonsAdd}
              </button>
            </div>
          </label>
          <p className="text-xs text-dim">{m.commonsHint}</p>
          <ErrorText error={urlError} />
        </form>
      )}
    </div>
  )
}

function ModuleItem({
  lesson,
  module,
  readOnly,
  controls,
}: {
  lesson: LessonOut
  module: ModuleOut
  readOnly: boolean
  controls: ReactNode
}) {
  const t = editor.modules
  const lessonId = lesson.id
  const [update] = useUpdateModuleMutation()
  const [remove] = useDeleteModuleMutation()
  const [reorder] = useReorderCardsMutation()
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [dropping, setDropping] = useState(false)
  const titleRef = useRef<HTMLInputElement>(null)
  const imports = useModuleImport(lessonId, module)

  const title = useAutosave({
    draftKey: `module:${module.id}:title`,
    server: module.title,
    disabled: readOnly,
    isValid: (v) => v.trim() !== '',
    save: (value) => update({ lessonId, id: module.id, patch: { title: value.trim() } }).unwrap(),
  })
  const minutes = useAutosave({
    draftKey: `module:${module.id}:minutes`,
    server: module.duration_min,
    disabled: readOnly,
    delay: 0,
    save: (value) => update({ lessonId, id: module.id, patch: { duration_min: value } }).unwrap(),
  })

  useEffect(() => {
    if (takeFocus(module.id)) titleRef.current?.select()
  }, [module.id])

  const cards = [...module.cards].sort((a, b) => a.position - b.position)
  const sortable = useSortable(
    cards.map((c) => c.id),
    (ids) => {
      setError(null)
      tracked(`order:${module.id}`, () => reorder({ lessonId, moduleId: module.id, ids }).unwrap()).catch((err: unknown) =>
        setError(errorMessage(err)),
      )
    },
  )
  const byId = new Map(cards.map((c) => [c.id, c]))

  const del = async () => {
    if (module.cards.length > 0 && !window.confirm(t.confirmDelete(module.cards.length))) return
    setDeleting(true)
    try {
      await tracked(`module-del:${module.id}`, () => remove({ lessonId, id: module.id }).unwrap())
    } catch (err) {
      setError(errorMessage(err))
      setDeleting(false)
    }
  }

  const hasFiles = (e: DragEvent) => e.dataTransfer.types.includes('Files')
  const dropProps = readOnly
    ? {}
    : {
        onDragOver: (e: DragEvent) => {
          if (!hasFiles(e)) return
          e.preventDefault()
          e.dataTransfer.dropEffect = 'copy'
          setDropping(true)
        },
        onDragLeave: (e: DragEvent) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropping(false)
        },
        onDrop: (e: DragEvent) => {
          if (!hasFiles(e)) return
          e.preventDefault()
          setDropping(false)
          for (const file of e.dataTransfer.files) imports.addFile(file)
        },
      }

  return (
    <div
      {...dropProps}
      className={`relative flex flex-col gap-3 rounded-2xl border p-3 transition-colors md:p-4 ${
        dropping ? 'border-accent bg-accent-soft/40' : 'border-line-soft'
      }`}
    >
      <div className="flex flex-wrap items-center gap-1">
        {controls}
        <input
          ref={titleRef}
          aria-label={t.name}
          value={title.value}
          disabled={readOnly}
          maxLength={200}
          onChange={(e) => title.set(e.target.value)}
          onBlur={title.flush}
          className={inlineField}
        />
        <select
          aria-label={t.minutes}
          value={minutes.value}
          disabled={readOnly}
          onChange={(e) => minutes.set(Number(e.target.value))}
          className={`${field} h-10 w-[84px] px-2 text-sm`}
        >
          {MINUTES.map((n) => (
            <option key={n} value={n}>
              {t.minutesLabel(n)}
            </option>
          ))}
        </select>
        {!readOnly && (
          <button type="button" aria-label={t.deleteModule} title={t.deleteModule} disabled={deleting} onClick={() => void del()} className={iconButton}>
            {deleting ? <Spinner /> : '✕'}
          </button>
        )}
      </div>
      <FieldStatus status={title.status} error={title.error} />
      <PendingMark id={module.id} />
      <ErrorText error={error} />

      {cards.length === 0 && imports.items.length === 0 && (
        <p className="rounded-[14px] border border-dashed border-line p-4 text-center text-sm text-dim">{readOnly ? editor.cards.emptyShort : editor.cards.empty}</p>
      )}
      {cards.length > 0 && (
        <ul className="flex flex-col gap-2">
          {sortable.order.map((id, index) => {
            const c = byId.get(id)
            if (!c) return null
            return (
              <li
                key={id}
                id={`card-${id}`}
                ref={sortable.itemRef(id)}
                className={`rounded-[14px] ${sortable.dragging === id ? 'opacity-70 shadow-lg ring-2 ring-accent' : ''}`}
              >
                <CardItem
                  lessonId={lessonId}
                  card={c}
                  readOnly={readOnly}
                  controls={<SortControls sortable={sortable} id={id} index={index} count={cards.length} disabled={readOnly} />}
                />
              </li>
            )
          })}
        </ul>
      )}
      {imports.items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {imports.items.map((item) => (
            <ImportRow key={item.key} item={item} onDismiss={() => imports.dismiss(item.key)} />
          ))}
        </ul>
      )}
      {!readOnly && (
        <>
          <AddBar
            onText={() => void imports.addText().catch((err: unknown) => setError(errorMessage(err)))}
            onFiles={(files) => files.forEach(imports.addFile)}
            onCommons={imports.addCommons}
          />
          {dropping && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-oil/70 text-lg font-semibold text-accent">
              {editor.cards.dropActive}
            </div>
          )}
          <p className="hidden text-center text-xs text-dim md:block">{editor.cards.drop}</p>
        </>
      )}
    </div>
  )
}

/** Модулі однієї частини уроку (укриття або основна) з картками. */
export default function ModulesSection({ lesson, part, readOnly }: { lesson: LessonOut; part: ModulePart; readOnly: boolean }) {
  const t = editor.modules
  const modules = lesson.modules.filter((m) => m.part === part).sort((a, b) => a.position - b.position)
  const [create] = useCreateModuleMutation()
  const [reorder] = useReorderModulesMutation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Id нового модуля фіксуємо до успіху: повтор після обриву мережі не створить дубля.
  const idRef = useRef(generateId())

  const sortable = useSortable(
    modules.map((m) => m.id),
    (ids) => {
      setError(null)
      tracked(`order:${part}`, () => reorder({ lessonId: lesson.id, part, ids }).unwrap()).catch((err: unknown) =>
        setError(errorMessage(err)),
      )
    },
  )
  const byId = new Map(modules.map((m) => [m.id, m]))

  const add = async () => {
    setBusy(true)
    setError(null)
    const id = idRef.current
    try {
      focusOnMount(id)
      await tracked(`module:${id}`, () =>
        create({
          lessonId: lesson.id,
          id,
          part,
          position: nextPosition(modules),
          title: t.defaultTitle(modules.length + 1),
          duration_min: 4,
        }).unwrap(),
      )
      idRef.current = generateId()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section id={`part-${part}`} className={card}>
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{part === 'shelter' ? t.shelter : t.main}</h2>
        <p className="text-sm text-dim">{part === 'shelter' ? t.shelterHint : t.mainHint}</p>
      </div>
      {modules.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {sortable.order.map((id, index) => {
            const m = byId.get(id)
            if (!m) return null
            return (
              <li
                key={id}
                id={`module-${id}`}
                ref={sortable.itemRef(id)}
                className={`rounded-2xl ${sortable.dragging === id ? 'opacity-70 shadow-lg ring-2 ring-accent' : ''}`}
              >
                <ModuleItem
                  lesson={lesson}
                  module={m}
                  readOnly={readOnly}
                  controls={<SortControls sortable={sortable} id={id} index={index} count={modules.length} disabled={readOnly} />}
                />
              </li>
            )
          })}
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
