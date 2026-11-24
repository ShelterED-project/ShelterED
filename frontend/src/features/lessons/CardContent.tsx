import type { PackCard } from '@/shared/db/packTypes'
import Markdown from '@/shared/ui/Markdown'
import { cardField } from './cardField'
import MediaView from './MediaView'
import type { MediaSource } from './MediaView'
import { usePackMedia } from './usePackMedia'

interface CardContentProps {
  /** text, image або video */
  kind: string
  /** Текст картки, простий Markdown */
  text?: string
  /** Підпис медіа */
  caption?: string
  /** Звідки брати файл для image/video */
  media?: MediaSource
  /** Розмір і колір основного тексту */
  textClassName?: string
}

/**
 * Вміст однієї картки: медіа (для image/video) і текст. Чистий компонент: учень бере медіа
 * з «Рюкзака» (PackCardContent), вчитель у перегляді — з відповіді редактора (media.url).
 */
export function CardContent({
  kind,
  text = '',
  caption = '',
  media,
  textClassName = 'text-lg leading-7 text-muted',
}: CardContentProps) {
  const isMedia = kind === 'image' || kind === 'video'
  return (
    <div className="flex flex-col gap-4">
      {isMedia && <MediaView kind={kind} caption={caption} {...(media ?? { src: null })} />}
      {text && <Markdown text={text} className={textClassName} />}
    </div>
  )
}

/** Картка з пакета «Рюкзака»: медіа за media_asset_id з таблиці media, без мережі. */
export function PackCardContent({ card, textClassName }: { card: PackCard; textClassName?: string }) {
  const media = usePackMedia(card.media_asset_id)
  return (
    <CardContent
      kind={card.kind}
      text={cardField(card, 'text')}
      caption={cardField(card, 'caption')}
      media={media}
      textClassName={textClassName}
    />
  )
}
