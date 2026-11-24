import { useEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import MediaView from '@/features/lessons/MediaView'
import {
  errorMessage,
  lessonQueryApi,
  useAttachSubtitlesMutation,
  useDeleteCardMutation,
  useMediaQuery,
  useUpdateCardMutation,
} from '@/features/teacher/lessonEditorApi'
import type { CardMediaOut, CardOut } from '@/features/teacher/lessonEditorApi'
import { useMediaUploader } from '@/features/teacher/mediaUpload'
import { useAppDispatch } from '@/app/hooks'
import { generateId } from '@/shared/lib/uuid'
import Markdown from '@/shared/ui/Markdown'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import FieldStatus from './FieldStatus'
import { takeFocus } from './jump'
import { tracked } from './saveStatus'
import { field, iconButton, linkButton, textarea } from './styles'
import { useAutosave } from './useAutosave'

const t = editor.cards

function bodyText(card: CardOut, key: 'text' | 'caption'): string {
  const value = card.body[key]
  return typeof value === 'string' ? value : ''
}

type Format = 'bold' | 'italic' | 'list' | 'numbered' | 'heading'

const LINE_PREFIX: Record<'list' | 'numbered' | 'heading', RegExp> = {
  list: /^[-*]\s+/,
  numbered: /^\d{1,3}[.)]\s+/,
  heading: /^#{1,6}\s+/,
}

/** Розмітка для виділеного (простий Markdown карток, shared/ui/Markdown). */
function applyFormat(value: string, start: number, end: number, format: Format): { text: string; start: number; end: number } {
  if (format === 'bold' || format === 'italic') {
    const mark = format === 'bold' ? '**' : '*'
    const selected = value.slice(start, end)
    const text = value.slice(0, start) + mark + selected + mark + value.slice(end)
    return { text, start: start + mark.length, end: end + mark.length }
  }
  // Рядкові формати: до кожного виділеного рядка; повторне натискання прибирає.
  const lineStart = value.lastIndexOf('\n', start - 1) + 1
  const nextBreak = value.indexOf('\n', end)
  const lineEnd = nextBreak === -1 ? value.length : nextBreak
  const lines = value.slice(lineStart, lineEnd).split('\n')
  const re = LINE_PREFIX[format]
  const remove = lines.every((line) => re.test(line))
  const changed = lines.map((line, i) => {
    const bare = line.replace(LINE_PREFIX.list, '').replace(LINE_PREFIX.numbered, '').replace(LINE_PREFIX.heading, '')
    if (remove) return bare
    return (format === 'list' ? '- ' : format === 'numbered' ? `${i + 1}. ` : '## ') + bare
  })
  const block = changed.join('\n')
  const text = value.slice(0, lineStart) + block + value.slice(lineEnd)
  // Без виділення — курсор у кінець рядка, щоб одразу писати; з виділенням — виділяємо змінене.
  return { text, start: start === end ? lineStart + block.length : lineStart, end: lineStart + block.length }
}

const FORMATS: { format: Format; label: string; title: string; className: string }[] = [
  { format: 'bold', label: 'Ж', title: t.format.bold, className: 'font-bold' },
  { format: 'italic', label: 'К', title: t.format.italic, className: 'italic' },
  { format: 'list', label: '•', title: t.format.list, className: 'text-lg' },
  { format: 'numbered', label: '1.', title: t.format.numbered, className: '' },
  { format: 'heading', label: 'H', title: t.format.heading, className: 'font-heading' },
]

function Toolbar({ inputRef, value, onChange }: { inputRef: RefObject<HTMLTextAreaElement | null>; value: string; onChange: (v: string) => void }) {
  const apply = (format: Format) => {
    const el = inputRef.current
    if (!el) return
    const next = applyFormat(value, el.selectionStart, el.selectionEnd, format)
    onChange(next.text)
    requestAnimationFrame(() => {
      el.focus()
      el.setSelectionRange(next.start, next.end)
    })
  }
  return (
    <div role="toolbar" aria-label={t.previewLabel} className="flex gap-1">
      {FORMATS.map((f) => (
        <button
          key={f.format}
          type="button"
          title={f.title}
          aria-label={f.title}
          // Не забираємо фокус і виділення з поля.
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => apply(f.format)}
          className={`${iconButton} size-9 border border-line ${f.className}`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}

const MARKUP = /\*|^#{1,6}\s|^[-*]\s|^\d{1,3}[.)]\s/m

function TextCard({ lessonId, card, readOnly }: { lessonId: string; card: CardOut; readOnly: boolean }) {
  const [update] = useUpdateCardMutation()
  const ref = useRef<HTMLTextAreaElement>(null)
  const text = useAutosave({
    draftKey: `card:${card.id}:text`,
    server: bodyText(card, 'text'),
    disabled: readOnly,
    save: (value) => update({ lessonId, id: card.id, body: { ...card.body, text: value } }).unwrap(),
  })

  useEffect(() => {
    if (takeFocus(card.id)) ref.current?.focus()
  }, [card.id])

  // Висота під текст: без прокрутки всередині поля.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight + 2}px`
  }, [text.value])

  return (
    <div className="flex flex-col gap-2">
      {!readOnly && <Toolbar inputRef={ref} value={text.value} onChange={text.set} />}
      <textarea
        ref={ref}
        aria-label={t.placeholder}
        placeholder={t.placeholder}
        value={text.value}
        disabled={readOnly}
        maxLength={20000}
        onChange={(e) => text.set(e.target.value)}
        onBlur={text.flush}
        className={`${textarea} resize-none overflow-hidden`}
      />
      <FieldStatus status={text.status} error={text.error} />
      {MARKUP.test(text.value) && (
        <div className="flex flex-col gap-1 rounded-[12px] border border-line-soft bg-oil/40 p-3">
          <p className="text-xs text-dim">{t.previewLabel}</p>
          <Markdown text={text.value} className="text-[15px] leading-[22.5px] text-muted" />
        </div>
      )}
    </div>
  )
}

/** Відео, яке стискає сервер: опитуємо стан, поки не стане ready/failed, потім оновлюємо урок. */
function Processing({ lessonId, media }: { lessonId: string; media: CardMediaOut }) {
  const dispatch = useAppDispatch()
  const { data } = useMediaQuery(media.id, { pollingInterval: 5000 })
  const status = data?.processing_status ?? media.processing_status
  useEffect(() => {
    if (data && data.processing_status !== 'processing') {
      dispatch(lessonQueryApi.util.invalidateTags([{ type: 'Lesson', id: lessonId }]))
    }
  }, [data, dispatch, lessonId])

  return (
    <p role="status" className="flex items-center gap-3 rounded-2xl border border-line bg-surface-2 p-5 text-sm text-muted">
      {status === 'failed' ? (
        editor.media.processingFailed
      ) : (
        <>
          <Spinner className="text-accent" />
          {editor.media.processing}
        </>
      )}
    </p>
  )
}

function Subtitles({ lessonId, media, readOnly }: { lessonId: string; media: CardMediaOut; readOnly: boolean }) {
  const s = editor.subtitles
  const upload = useMediaUploader()
  const [attach] = useAttachSubtitlesMutation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  // Id файла субтитрів фіксуємо до успіху: повтор не створить дубля.
  const idRef = useRef(generateId())

  const pick = async (file: File | undefined) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.vtt') || file.size > 200 * 1024) {
      setError(s.bad)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await tracked(`subs:${media.id}`, async () => {
        const subs = await upload({ id: idRef.current, kind: 'subtitles', file, mime: 'text/vtt', lessonId })
        await attach({ lessonId, videoId: media.id, subtitlesId: subs.id }).unwrap()
      })
      idRef.current = generateId()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  const has = Boolean(media.subtitles_id)
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        {has ? (
          <span className="text-sm font-semibold text-safe">{s.has}</span>
        ) : (
          <span className="rounded-md bg-accent-soft px-2 py-1 text-xs font-semibold text-accent">{s.missing}</span>
        )}
        {!readOnly && (
          <label className={`${linkButton} cursor-pointer`}>
            {busy ? <Spinner /> : null}
            {busy ? s.uploading : has ? s.replace : s.add}
            <input
              ref={input}
              type="file"
              accept=".vtt,text/vtt"
              disabled={busy}
              onChange={(e) => void pick(e.target.files?.[0])}
              className="sr-only"
            />
          </label>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm font-semibold text-accent">
          {error}
        </p>
      )}
    </div>
  )
}

function MediaCard({ lessonId, card, readOnly }: { lessonId: string; card: CardOut; readOnly: boolean }) {
  const [update] = useUpdateCardMutation()
  const caption = useAutosave({
    draftKey: `card:${card.id}:caption`,
    server: bodyText(card, 'caption'),
    disabled: readOnly,
    save: (value) => update({ lessonId, id: card.id, body: { ...card.body, caption: value } }).unwrap(),
  })
  const media = card.media
  const kind = card.kind === 'video' ? 'video' : 'image'

  return (
    <div className="flex flex-col gap-3">
      {media && media.processing_status && media.processing_status !== 'ready' ? (
        <Processing lessonId={lessonId} media={media} />
      ) : (
        <MediaView kind={kind} src={media?.url ?? null} subtitlesSrc={media?.subtitles?.url ?? null} />
      )}
      {media?.attribution && (
        <p className="text-xs text-dim">
          {t.source}{' '}
          {media.source_url ? (
            <a href={media.source_url} target="_blank" rel="noreferrer" className="underline hover:text-parchment">
              {media.attribution}
            </a>
          ) : (
            media.attribution
          )}
        </p>
      )}
      <input
        aria-label={t.caption}
        placeholder={t.captionPlaceholder}
        value={caption.value}
        disabled={readOnly}
        maxLength={1000}
        onChange={(e) => caption.set(e.target.value)}
        onBlur={caption.flush}
        className={field}
      />
      <FieldStatus status={caption.status} error={caption.error} />
      {kind === 'video' && media && <Subtitles lessonId={lessonId} media={media} readOnly={readOnly} />}
    </div>
  )
}

/** Картка модуля: текст з форматуванням або медіа з підписом. Усе зберігається саме. */
export default function CardItem({
  lessonId,
  card,
  readOnly,
  controls,
}: {
  lessonId: string
  card: CardOut
  readOnly: boolean
  /** Ручка й ↑/↓ */
  controls: ReactNode
}) {
  const [remove] = useDeleteCardMutation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const del = async () => {
    setBusy(true)
    setError(null)
    try {
      await tracked(`card-del:${card.id}`, () => remove({ lessonId, id: card.id }).unwrap())
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-[14px] border border-line-soft bg-surface p-3">
      <div className="flex items-center gap-2">
        {controls}
        <span className="flex-1 text-xs font-semibold tracking-[0.96px] text-dim uppercase">{t.kinds[card.kind] ?? card.kind}</span>
        {!readOnly && (
          <button type="button" aria-label={t.deleteCard} title={t.deleteCard} disabled={busy} onClick={() => void del()} className={iconButton}>
            {busy ? <Spinner /> : '✕'}
          </button>
        )}
      </div>
      {card.kind === 'text' ? (
        <TextCard lessonId={lessonId} card={card} readOnly={readOnly} />
      ) : (
        <MediaCard lessonId={lessonId} card={card} readOnly={readOnly} />
      )}
      {error && (
        <p role="alert" className="text-sm font-semibold text-accent">
          {error}
        </p>
      )}
    </div>
  )
}
