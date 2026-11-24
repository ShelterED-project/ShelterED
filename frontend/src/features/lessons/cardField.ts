import type { PackCard } from '@/shared/db/packTypes'

/** Рядкове поле body картки (text — Markdown, caption — підпис медіа). */
export function cardField(card: Pick<PackCard, 'body'>, field: 'text' | 'caption'): string {
  const value = card.body[field]
  return typeof value === 'string' ? value : ''
}

/** Markdown картки як простий рядок — для однорядкових підписів і превʼю «Далі». */
export function plainText(markdown: string): string {
  return markdown
    .replace(/^\s*(#{1,6}\s+|[-*]\s+|\d+\.\s+)/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
}
