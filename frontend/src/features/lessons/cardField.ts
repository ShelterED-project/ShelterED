import type { PackCard } from '@/shared/db/packTypes'

/** Рядкове поле body картки (text — Markdown, caption — підпис медіа). */
export function cardField(card: Pick<PackCard, 'body'>, field: 'text' | 'caption'): string {
  const value = card.body[field]
  return typeof value === 'string' ? value : ''
}
