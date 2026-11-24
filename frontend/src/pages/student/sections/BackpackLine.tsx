import { useBackpackStatus } from '@/features/packs/useBackpackStatus'
import { backpackLine } from './backpackText'

/** Один рядок: «Урок збережено на телефоні ✓ (4,2 МБ)» або «Зберігаю відео… 2 з 3». */
export default function BackpackLine({ className = '' }: { className?: string }) {
  const line = backpackLine(useBackpackStatus())
  if (!line) return null
  return (
    <p role="status" className={`text-sm leading-5 font-semibold ${line.done ? 'text-safe' : 'text-accent'} ${className}`}>
      {line.text}
    </p>
  )
}
