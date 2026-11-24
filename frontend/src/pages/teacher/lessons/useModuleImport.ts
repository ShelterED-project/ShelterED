import { useRef, useState } from 'react'
import { errorCode, errorMessage, isNotAvailable, nextPosition, useCreateCardMutation, useImportCommonsMutation } from '@/features/teacher/lessonEditorApi'
import type { CardKind, MediaOut, ModuleOut } from '@/features/teacher/lessonEditorApi'
import { ImageUnsupported, prepareImage } from '@/features/teacher/imagePrep'
import { useMediaUploader } from '@/features/teacher/mediaUpload'
import { generateId } from '@/shared/lib/uuid'
import { editor } from './content'
import { focusOnMount } from './jump'
import { tracked } from './saveStatus'

const MB = 1024 * 1024
const VIDEO_MAX = 30 * MB
const SOURCE_MAX = 300 * MB
const DIRECT_VIDEO = new Set(['video/mp4', 'video/webm'])

export interface ImportItem {
  key: string
  label: string
  /** Що відбувається зараз (текст для вчителя) */
  status: string
  /** 0..1 або null, якщо прогрес невідомий */
  progress: number | null
  error: string | null
  /** Підсумок без помилки (напр. скільки сторінок PDF додано) */
  note: string | null
  retry: (() => void) | null
}

/** Помилка, текст якої вже зрозумілий вчителю. */
class Friendly extends Error {}

function fileKind(file: File): 'image' | 'video' | 'pdf' | null {
  if (file.type.startsWith('image/')) return 'image'
  if (file.type.startsWith('video/')) return 'video'
  if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) return 'pdf'
  return null
}

/** Commons: сторінка файла (wiki/File:…) або прямий файл upload.wikimedia.org. */
export function isCommonsUrl(url: string): boolean {
  try {
    const u = new URL(url.trim())
    return /(^|\.)commons\.wikimedia\.org$/.test(u.hostname) || u.hostname === 'upload.wikimedia.org'
  } catch {
    return false
  }
}

/**
 * Додавання медіа в модуль: файли (фото, відео, PDF) і посилання з Wikimedia Commons. Кожен
 * файл — рядок у черзі з прогресом; id медіа й картки фіксуються на старті, тож «Спробувати ще»
 * нічого не дублює (принцип 3).
 */
export function useModuleImport(lessonId: string, module: ModuleOut) {
  const [items, setItems] = useState<ImportItem[]>([])
  const upload = useMediaUploader()
  const [createCard] = useCreateCardMutation()
  const [importCommons] = useImportCommonsMutation()
  const t = editor.media
  // Позиції нових карток: сервер не перенумеровує, а кеш уроку оновлюється із запізненням.
  const posRef = useRef(0)
  const takePosition = () => {
    const pos = Math.max(nextPosition(module.cards), posRef.current)
    posRef.current = pos + 1
    return pos
  }

  const patch = (key: string, change: Partial<ImportItem>) =>
    setItems((prev) => prev.map((item) => (item.key === key ? { ...item, ...change } : item)))
  const remove = (key: string) => setItems((prev) => prev.filter((item) => item.key !== key))

  const start = (label: string, run: (key: string) => Promise<string | null>) => {
    const key = generateId()
    const attempt = async () => {
      patch(key, { error: null, note: null, retry: null, progress: null, status: t.preparing })
      try {
        const note = await tracked(`import:${key}`, () => run(key))
        if (note) patch(key, { note, status: '', progress: null })
        else remove(key)
      } catch (err) {
        const message = err instanceof Friendly ? err.message : errorMessage(err)
        patch(key, { error: message, progress: null, retry: () => void attempt() })
      }
    }
    setItems((prev) => [...prev, { key, label, status: t.preparing, progress: null, error: null, note: null, retry: null }])
    void attempt()
  }

  const addCard = async (id: string, position: number, kind: CardKind, media: MediaOut, caption: string) => {
    await createCard({ lessonId, moduleId: module.id, id, position, kind, body: { caption }, media_asset_id: media.id }).unwrap()
  }

  const uploadVideo = async (key: string, file: File, mediaId: string): Promise<MediaOut> => {
    let compressed: Blob | null = null
    try {
      patch(key, { status: t.compressing(0), progress: 0 })
      const { compressVideo } = await import('@/features/teacher/videoCompress')
      compressed = await compressVideo(file, (share) => patch(key, { status: t.compressing(Math.round(share * 100)), progress: share }))
    } catch {
      // Браузер не вміє стиснути (або файл не прочитався): хай стискає сервер.
      compressed = null
    }
    const onProgress = (share: number) => patch(key, { status: t.uploading(Math.round(share * 100)), progress: share })
    if (compressed) {
      // Якщо оригінал і так менший і підходить серверу — беремо його.
      const useOriginal = DIRECT_VIDEO.has(file.type) && file.size <= Math.min(compressed.size, VIDEO_MAX)
      const blob = useOriginal ? file : compressed
      if (blob.size > VIDEO_MAX) throw new Friendly(t.tooLong)
      return upload({ id: mediaId, kind: 'video', file: blob, mime: blob.type || 'video/mp4', lessonId, onProgress })
    }
    if (file.size > SOURCE_MAX) throw new Friendly(t.tooBig)
    patch(key, { status: t.serverCompress, progress: 0 })
    try {
      return await upload({ id: mediaId, kind: 'video_source', file, mime: file.type || 'video/mp4', lessonId, onProgress })
    } catch (err) {
      // Сервер ще не приймає оригінали (404 або 422 на невідомий kind): пробуємо як є.
      const unknownKind = isNotAvailable(err) || errorCode(err) === 'VALIDATION_ERROR'
      if (!unknownKind) throw err
      if (DIRECT_VIDEO.has(file.type) && file.size <= VIDEO_MAX) {
        return upload({ id: mediaId, kind: 'video', file, lessonId, onProgress })
      }
      throw new Friendly(t.noServerCompress)
    }
  }

  const addFile = (file: File) => {
    const kind = fileKind(file)
    if (!kind) {
      setItems((prev) => [
        ...prev,
        { key: generateId(), label: file.name, status: '', progress: null, error: t.unsupported, note: null, retry: null },
      ])
      return
    }
    if (kind === 'pdf') return addPdf(file)
    const mediaId = generateId()
    const cardId = generateId()
    let position: number | null = null
    start(file.name, async (key) => {
      let media: MediaOut
      if (kind === 'image') {
        let blob: Blob
        try {
          blob = await prepareImage(file)
        } catch (err) {
          if (err instanceof ImageUnsupported) throw new Friendly(t.badImage)
          throw err
        }
        media = await upload({
          id: mediaId,
          kind: 'image',
          file: blob,
          lessonId,
          onProgress: (share) => patch(key, { status: t.uploading(Math.round(share * 100)), progress: share }),
        })
      } else {
        media = await uploadVideo(key, file, mediaId)
      }
      patch(key, { status: t.creating, progress: null })
      position ??= takePosition()
      await addCard(cardId, position, kind, media, '')
      return null
    })
  }

  const addPdf = (file: File) => {
    // Уже створені сторінки (номер → готово): «Спробувати ще» продовжує з місця збою.
    const done = new Set<number>()
    const ids = new Map<number, { media: string; card: string; position: number }>()
    start(file.name, async (key) => {
      patch(key, { status: t.readingPdf })
      const { pdfPages } = await import('@/features/teacher/pdfPages')
      let total = 0
      let all = 0
      try {
        for await (const page of pdfPages(file)) {
          total = page.total
          all = page.pagesInFile
          if (done.has(page.number)) continue
          patch(key, { status: t.page(page.number, page.total), progress: (page.number - 1) / page.total })
          let pageIds = ids.get(page.number)
          if (!pageIds) {
            pageIds = { media: generateId(), card: generateId(), position: takePosition() }
            ids.set(page.number, pageIds)
          }
          const media = await upload({ id: pageIds.media, kind: 'image', file: page.image, lessonId })
          await addCard(pageIds.card, pageIds.position, 'image', media, page.caption)
          done.add(page.number)
        }
      } catch (err) {
        if ((err as { status?: unknown })?.status !== undefined) throw err
        throw new Friendly(t.badPdf)
      }
      return all > total ? t.pdfCapped(total, all) : t.pdfDone(total)
    })
  }

  const addCommons = (url: string) => {
    const mediaId = generateId()
    const cardId = generateId()
    let position: number | null = null
    start(url.replace(/^https?:\/\//, '').slice(0, 60), async (key) => {
      patch(key, { status: t.commonsImporting })
      let media: MediaOut
      try {
        media = await importCommons({ id: mediaId, url: url.trim() }).unwrap()
      } catch (err) {
        if (isNotAvailable(err)) throw new Friendly(t.commonsUnavailable)
        throw err
      }
      position ??= takePosition()
      await addCard(cardId, position, media.kind === 'video' ? 'video' : 'image', media, '')
      return null
    })
  }

  /** Порожня текстова картка: створюємо одразу й ставимо в неї курсор. */
  const addText = async () => {
    const id = generateId()
    focusOnMount(id)
    await tracked(`card:${id}`, () =>
      createCard({ lessonId, moduleId: module.id, id, position: takePosition(), kind: 'text', body: { text: '' } }).unwrap(),
    )
  }

  return { items, addFile, addCommons, addText, dismiss: remove }
}
