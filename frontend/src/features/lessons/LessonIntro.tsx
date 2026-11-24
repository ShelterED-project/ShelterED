import Markdown from '@/shared/ui/Markdown'
import { intro as texts } from './content'

/**
 * Вступ до уроку від вчителя (укриттєва частина, lesson.shelter_part): що робимо в укритті.
 * Показується над першою карткою, без окремого екрана й зайвого натискання.
 */
export default function LessonIntro({ text }: { text: string }) {
  if (!text.trim()) return null
  return (
    <aside className="flex flex-col gap-1.5 rounded-2xl border border-accent/40 bg-accent-soft px-4 py-3">
      <p className="text-xs leading-4 font-semibold tracking-[0.96px] text-accent uppercase">{texts.eyebrow}</p>
      <Markdown text={text} className="text-base leading-6 text-parchment" />
    </aside>
  )
}
