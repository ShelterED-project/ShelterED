import { useRef, useState } from 'react'
import { media as texts } from './content'

export interface MediaSource {
  /** URL файла (/media/...); null — URL невідомий (немає в маніфесті) */
  src: string | null
  /** URL VTT-субтитрів відео */
  subtitlesSrc?: string | null
  /**
   * Файл можна показати: він у кеші пристрою або є мережа. false — одразу показуємо пояснення
   * замість порожнього плеєра.
   */
  available?: boolean
  /** Ще читаємо з пристрою, куди вести: показуємо порожню рамку без тексту */
  loading?: boolean
}

interface MediaViewProps extends MediaSource {
  kind: 'image' | 'video'
  /** Підпис медіа (звичайний текст), він же alt для зображення */
  caption?: string
}

function Fallback({ caption, text }: { caption?: string; text: string }) {
  return (
    <div role="status" className="flex flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-5">
      {caption && <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">{caption}</p>}
      <p className="text-sm leading-5 text-muted">{text}</p>
    </div>
  )
}

/**
 * Зображення чи відео картки. Відео без автозапуску, з субтитрами, увімкненими за замовчуванням
 * (тихий режим), playsInline для iOS. Якщо файлу немає на пристрої й немає мережі або він не
 * відкрився — дружнє пояснення з підписом. Компонент чистий: URL дає викликач
 * (учень — з «Рюкзака» через usePackMedia, вчитель — з відповіді редактора).
 */
export default function MediaView({ kind, src, subtitlesSrc, available = true, loading = false, caption }: MediaViewProps) {
  // Який файл не відкрився: новий src — нова спроба.
  const [brokenSrc, setBrokenSrc] = useState<string | null>(null)
  const broken = src !== null && brokenSrc === src
  const videoRef = useRef<HTMLVideoElement>(null)

  if (loading) return <div aria-hidden="true" className="aspect-video w-full rounded-2xl border border-line bg-surface-2" />
  if (!src || !available) return <Fallback caption={caption} text={texts.offline[kind]} />
  if (broken) return <Fallback caption={caption} text={texts.broken[kind]} />

  if (kind === 'image') {
    return (
      <figure className="flex flex-col gap-2">
        <img
          src={src}
          alt={caption || texts.imageAlt}
          decoding="async"
          onError={() => setBrokenSrc(src)}
          className="max-h-[60vh] w-full rounded-2xl border border-line bg-oil object-contain"
        />
        {caption && <figcaption className="text-sm leading-5 text-muted">{caption}</figcaption>}
      </figure>
    )
  }

  // Субтитри завжди показуємо: атрибут default не всі браузери поважають для доданих пізніше доріжок.
  const showCaptions = () => {
    const tracks = videoRef.current?.textTracks
    if (tracks && tracks.length > 0 && tracks[0]) tracks[0].mode = 'showing'
  }

  return (
    <figure className="flex flex-col gap-2">
      <video
        ref={videoRef}
        src={src}
        controls
        playsInline
        preload="metadata"
        onLoadedMetadata={showCaptions}
        onError={() => setBrokenSrc(src)}
        className="aspect-video w-full rounded-2xl border border-line bg-black"
      >
        {subtitlesSrc && <track kind="subtitles" srcLang="uk" label={texts.subtitles} src={subtitlesSrc} default />}
      </video>
      {caption && <figcaption className="text-sm leading-5 text-muted">{caption}</figcaption>}
      {!subtitlesSrc && <p className="text-xs leading-4 text-dim">{texts.noCaptions}</p>}
    </figure>
  )
}
