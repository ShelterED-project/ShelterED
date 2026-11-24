// Імпорт PDF (презентація, збережена як PDF): кожна сторінка → зображення для картки уроку,
// текст сторінки (якщо є) — для підпису. pdf.js (Apache-2.0) і його воркер підвантажуються
// лише тут, у основний бандл не потрапляють.
import { canvasToImage } from './imagePrep'

export const PDF_MAX_PAGES = 40
const MAX_WIDTH = 1280
/** Підпис до картки — короткий: довгий текст сторінки обрізаємо. */
export const PDF_CAPTION_MAX = 500

export interface PdfPage {
  /** Номер сторінки, з 1 */
  number: number
  /** Скільки сторінок імпортуємо (не більше PDF_MAX_PAGES) */
  total: number
  /** Скільки сторінок у файлі */
  pagesInFile: number
  image: Blob
  /** Текст сторінки без зайвих пробілів (може бути порожнім) */
  text: string
  /** Текст сторінки для підпису картки (обрізаний) */
  caption: string
}

function clean(text: string): string {
  return text
    .replace(/[ \t ]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function captionFrom(text: string): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > PDF_CAPTION_MAX ? `${flat.slice(0, PDF_CAPTION_MAX - 1).trimEnd()}…` : flat
}

/** Сторінки PDF по черзі (щоб не тримати в памʼяті всі зображення одразу). */
export async function* pdfPages(file: Blob): AsyncGenerator<PdfPage> {
  const [pdfjs, worker] = await Promise.all([import('pdfjs-dist'), import('pdfjs-dist/build/pdf.worker.min.mjs?url')])
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default
  const task = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) })
  const doc = await task.promise
  try {
    const total = Math.min(doc.numPages, PDF_MAX_PAGES)
    for (let number = 1; number <= total; number++) {
      const page = await doc.getPage(number)
      const base = page.getViewport({ scale: 1 })
      const viewport = page.getViewport({ scale: Math.min(MAX_WIDTH / base.width, 3) })
      const canvas = document.createElement('canvas')
      canvas.width = Math.floor(viewport.width)
      canvas.height = Math.floor(viewport.height)
      // Білий фон: прозорі ділянки слайда інакше стануть чорними в JPEG і темними на тлі застосунку.
      await page.render({ canvas, viewport, background: '#ffffff' }).promise
      const image = await canvasToImage(canvas)

      const content = await page.getTextContent()
      const text = clean(
        content.items.map((item) => ('str' in item ? item.str + (item.hasEOL ? '\n' : ' ') : '')).join(''),
      )
      page.cleanup()
      yield { number, total, pagesInFile: doc.numPages, image, text, caption: captionFrom(text) }
    }
  } finally {
    await task.destroy()
  }
}
