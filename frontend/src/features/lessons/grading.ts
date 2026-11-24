import type { PackQuestion, PackTest } from '@/shared/db/packTypes'
import type { QuestionAnswer, TestAnswers } from '@/shared/db/types'

/**
 * Перевірка відповіді так само, як на сервері (backend/app/services/grading.py): питання
 * зараховане лише повністю правильною відповіддю, часткових балів немає.
 */

// Різні апострофи (українська клавіатура, автозаміна) — один символ.
const APOSTROPHES = /[’ʼ‘`´ʹ′‛]/g

/** Для порівняння короткої відповіді: апострофи → ', NFKC, без зайвих пробілів і регістру. */
export function normalizeText(value: string): string {
  return value.replace(APOSTROPHES, "'").normalize('NFKC').replace(/\s+/g, ' ').trim().toLowerCase()
}

function asList(answer: QuestionAnswer | undefined): string[] {
  return Array.isArray(answer) ? answer : []
}

function asPairs(answer: QuestionAnswer | undefined): Record<string, string> {
  return answer && !Array.isArray(answer) ? answer : {}
}

/** Чи учень відповів настільки, щоб перейти далі (для match — пара для кожного лівого). */
export function isAnswered(question: PackQuestion, answer: QuestionAnswer | undefined): boolean {
  if (question.kind === 'text') return (asList(answer)[0] ?? '').trim() !== ''
  if (question.kind === 'match') {
    const pairs = asPairs(answer)
    return question.options.every((left) => Boolean(pairs[left.id]))
  }
  return asList(answer).length > 0
}

/** Чи відповідь правильна. Без ключа (оцінюваний тест) — null: оцінить сервер. */
export function isCorrect(question: PackQuestion, answer: QuestionAnswer | undefined): boolean | null {
  const key = question.answer_key
  if (key == null) return null
  if (answer === undefined) return false
  if (question.kind === 'text') {
    const given = normalizeText(asList(answer)[0] ?? '')
    return given !== '' && Array.isArray(key) && key.some((k) => normalizeText(k) === given)
  }
  if (question.kind === 'match') {
    if (Array.isArray(key) || Array.isArray(answer)) return false
    const keyIds = Object.keys(key)
    return keyIds.length === Object.keys(answer).length && keyIds.every((left) => answer[left] === key[left])
  }
  if (!Array.isArray(key) || !Array.isArray(answer)) return false
  const chosen = new Set(answer)
  return chosen.size === new Set(key).size && key.every((id) => chosen.has(id))
}

/** Бали за тренувальний тест. Якщо хоч одне питання без ключа — null (оцінює сервер). */
export function scoreTest(test: PackTest, answers: TestAnswers): { points: number; max: number } | null {
  if (test.questions.some((q) => q.answer_key == null)) return null
  let points = 0
  let max = 0
  for (const q of test.questions) {
    max += q.points
    if (isCorrect(q, answers[q.id])) points += q.points
  }
  return { points, max }
}

/** Відповідь у формі протоколу (docs/sync-protocol.md): текст обрізаний, порожні не надсилаємо. */
export function toWireAnswers(test: PackTest, answers: TestAnswers): TestAnswers {
  const wire: TestAnswers = {}
  for (const q of test.questions) {
    const answer = answers[q.id]
    if (answer === undefined || !isAnswered(q, answer)) continue
    if (q.kind === 'text') wire[q.id] = [(asList(answer)[0] ?? '').trim().slice(0, 200)]
    else if (q.kind === 'match') {
      // Лише пари для лівих елементів цього питання.
      const pairs = asPairs(answer)
      wire[q.id] = Object.fromEntries(q.options.flatMap((left) => (pairs[left.id] ? [[left.id, pairs[left.id]]] : [])))
    } else wire[q.id] = asList(answer)
  }
  return wire
}
