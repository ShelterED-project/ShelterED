// Стискання відео в браузері перед завантаженням (Mediabunny, MPL-2.0, на WebCodecs):
// MP4 H.264 не більше 720p зі збереженням пропорцій, ~1,2 Мбіт/с, звук AAC ~96 кбіт/с,
// moov на початку файла (faststart), щоб відео починало грати до повного завантаження.
// Бібліотека підвантажується лише тут (динамічний import), в основний бандл вона не потрапляє.

const VIDEO_BITRATE = 1_200_000
const AUDIO_BITRATE = 96_000
const SHORT_SIDE = 720
const LONG_SIDE = 1280

/** Браузер не вміє стиснути це відео (немає WebCodecs чи потрібних кодеків). */
export class CompressUnsupported extends Error {}

const even = (n: number) => Math.max(2, Math.round(n / 2) * 2)

/**
 * Повертає стиснутий MP4. CompressUnsupported — стиснути в цьому браузері не можна (тоді
 * завантажуємо оригінал, і стискає сервер); інша помилка — файл не вдалося прочитати.
 */
export async function compressVideo(file: Blob, onProgress: (share: number) => void): Promise<Blob> {
  if (typeof VideoEncoder === 'undefined' || typeof VideoDecoder === 'undefined') throw new CompressUnsupported()
  const mb = await import('mediabunny')

  const input = new mb.Input({ formats: mb.ALL_FORMATS, source: new mb.BlobSource(file) })
  try {
    const video = await input.getPrimaryVideoTrack()
    if (!video) throw new Error('no video track')
    const audio = await input.getPrimaryAudioTrack()

    const w = video.displayWidth
    const h = video.displayHeight
    const scale = Math.min(1, SHORT_SIDE / Math.min(w, h), LONG_SIDE / Math.max(w, h))
    const width = even(w * scale)
    const height = even(h * scale)

    const quality = new mb.Quality({ bitrate: VIDEO_BITRATE })
    if (!(await mb.canEncodeVideo('avc', { width, height, quality }))) throw new CompressUnsupported()
    const audioQuality = new mb.Quality({ bitrate: AUDIO_BITRATE })
    if (audio && !(await mb.canEncodeAudio('aac', { quality: audioQuality }))) throw new CompressUnsupported()

    const target = new mb.BufferTarget()
    const output = new mb.Output({ format: new mb.Mp4OutputFormat({ fastStart: 'in-memory' }), target })
    const conversion = await mb.Conversion.init({
      input,
      output,
      tracks: 'primary',
      video: { codec: 'avc', width, height, fit: 'contain', quality, forceTranscode: true },
      audio: { codec: 'aac', quality: audioQuality },
      showWarnings: false,
    })
    // Звук не можна тихо загубити: якщо доріжку відкинуто, хай стискає сервер.
    const lostAudio = conversion.discardedTracks.some((d) => d.track.isAudioTrack() && d.reason !== 'discarded_by_user')
    if (!conversion.isValid || lostAudio) throw new CompressUnsupported()

    conversion.onProgress = (share) => onProgress(Math.min(1, share))
    await conversion.execute()
    if (!target.buffer) throw new Error('empty output')
    return new Blob([target.buffer], { type: 'video/mp4' })
  } finally {
    input.dispose()
  }
}
