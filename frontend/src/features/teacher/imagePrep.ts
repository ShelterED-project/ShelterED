// Підготовка зображень до завантаження: сервер приймає JPEG/PNG/WebP до 2 МБ і сам зберігає
// WebP з довшою стороною ≤ 1280 px. Великі фото з телефона зменшуємо ще в браузері, щоб вони
// пройшли ліміт і швидше відправились.

export const IMAGE_MAX_BYTES = 2 * 1024 * 1024
const MAX_SIDE = 1280
const ACCEPTED = new Set(['image/jpeg', 'image/png', 'image/webp'])

export class ImageUnsupported extends Error {}

function toBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality))
}

/**
 * Полотно → WebP (або JPEG, якщо браузер не кодує WebP) не більше 2 МБ: якщо завелике,
 * знижуємо якість.
 */
export async function canvasToImage(canvas: HTMLCanvasElement): Promise<Blob> {
  for (const quality of [0.85, 0.72, 0.6, 0.45]) {
    let blob = await toBlob(canvas, 'image/webp', quality)
    if (!blob || blob.type !== 'image/webp') blob = await toBlob(canvas, 'image/jpeg', quality)
    if (blob && blob.size <= IMAGE_MAX_BYTES) return blob
  }
  throw new ImageUnsupported('too large')
}

/** Файл, готовий до PUT /media/{id}?kind=image. */
export async function prepareImage(file: File): Promise<Blob> {
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    // Напр. HEIC з iPhone у браузері, що його не читає.
    throw new ImageUnsupported('unreadable')
  }
  try {
    const { width, height } = bitmap
    const scale = Math.min(1, MAX_SIDE / Math.max(width, height))
    if (scale === 1 && ACCEPTED.has(file.type) && file.size <= IMAGE_MAX_BYTES) return file
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new ImageUnsupported('no canvas')
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    return await canvasToImage(canvas)
  } finally {
    bitmap.close()
  }
}
