import type { PackOption, PackQuestion } from '@/shared/db/packTypes'
import type { QuestionAnswer } from '@/shared/db/types'

function optionText(options: PackOption[] | null | undefined, id: string): string {
  return options?.find((o) => o.id === id)?.text ?? id
}

/** Відповідь учня текстом (для розбору). */
export function answerText(question: PackQuestion, answer: QuestionAnswer | undefined): string[] {
  if (answer === undefined) return []
  if (question.kind === 'match') {
    if (Array.isArray(answer)) return []
    return question.options.flatMap((left) =>
      answer[left.id] ? [`${left.text} → ${optionText(question.right_options, answer[left.id] ?? '')}`] : [],
    )
  }
  if (!Array.isArray(answer)) return []
  if (question.kind === 'text') return answer[0]?.trim() ? [answer[0].trim()] : []
  return answer.map((id) => optionText(question.options, id))
}

/** Правильна відповідь текстом; для text — перший прийнятний варіант. Без ключа — порожньо. */
export function keyText(question: PackQuestion): string[] {
  const key = question.answer_key
  if (key == null) return []
  if (question.kind === 'match') {
    if (Array.isArray(key)) return []
    return question.options.map((left) => `${left.text} → ${optionText(question.right_options, key[left.id] ?? '')}`)
  }
  if (!Array.isArray(key)) return []
  if (question.kind === 'text') return key.slice(0, 1)
  return key.map((id) => optionText(question.options, id))
}
