import { useState } from 'react'
import { completeModule } from '@/features/lessons/completeStep'
import type { PackModule } from '@/shared/db/packTypes'
import { task } from '../content'
import { TaskFrame } from './TaskCard'

const primaryButton =
  'h-12 rounded-[10px] bg-accent px-7 text-[15px] font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:opacity-50'

/** Модуль: картки по одній, на останній модуль завершується й пишеться подія module_progress. */
export default function ModuleTask({ userId, lessonId, module }: { userId: string; lessonId: string; module: PackModule }) {
  const cards = [...module.cards].sort((a, b) => a.position - b.position)
  const [index, setIndex] = useState(0)
  const [saving, setSaving] = useState(false)

  const card = cards[index]
  const isLast = index >= cards.length - 1
  const text = typeof card?.body.text === 'string' ? card.body.text : ''

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
      {text && <p className="py-2 text-[17px] leading-[27px] whitespace-pre-line text-parchment">{text}</p>}
      <div className="flex flex-col gap-3 pt-[9px] md:flex-row md:justify-end">
        <button type="button" onClick={() => void advance()} disabled={saving} className={primaryButton}>
          {isLast ? task.finishModule : task.next}
        </button>
      </div>
    </TaskFrame>
  )
}
