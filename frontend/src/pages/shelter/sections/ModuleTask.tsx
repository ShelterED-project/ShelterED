import { useState } from 'react'
import { PackCardContent } from '@/features/lessons/CardContent'
import { completeModule } from '@/features/lessons/completeStep'
import LessonIntro from '@/features/lessons/LessonIntro'
import type { PackModule } from '@/shared/db/packTypes'
import { task } from '../content'
import { TaskFrame } from './TaskCard'

const primaryButton =
  'h-14 rounded-[10px] bg-accent px-7 text-base font-bold md:h-12 md:text-[15px] text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:opacity-50'

/**
 * Модуль: картки по одній, на останній модуль завершується й пишеться подія module_progress.
 * intro — вступ вчителя до уроку над першою карткою (лише на початку уроку).
 */
export default function ModuleTask({
  userId,
  lessonId,
  module,
  intro = '',
}: {
  userId: string
  lessonId: string
  module: PackModule
  intro?: string
}) {
  const cards = [...module.cards].sort((a, b) => a.position - b.position)
  const [index, setIndex] = useState(0)
  const [saving, setSaving] = useState(false)

  const card = cards[index]
  const isLast = index >= cards.length - 1

  const advance = async () => {
    if (!isLast) {
      setIndex(index + 1)
      return
    }
    setSaving(true)
    try {
      await completeModule(userId, lessonId, module.id)
    } finally {
      setSaving(false)
    }
  }

  return (
    <TaskFrame meta={cards.length > 0 ? task.moduleMeta(index + 1, cards.length) : undefined} title={module.title}>
      {index === 0 && <LessonIntro text={intro} />}
      {card && (
        <div className="py-2">
          <PackCardContent key={card.id} card={card} textClassName="text-[17px] leading-[27px] text-parchment" />
        </div>
      )}
      <div className="flex flex-col gap-3 pt-[9px] md:flex-row md:justify-end">
        <button type="button" onClick={() => void advance()} disabled={saving} className={primaryButton}>
          {isLast ? task.finishModule : task.next}
        </button>
      </div>
    </TaskFrame>
  )
}
