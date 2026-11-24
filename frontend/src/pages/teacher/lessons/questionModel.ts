import type { QuestionFields, QuestionKind, QuestionOption, QuestionOut } from '@/features/teacher/lessonEditorApi'
import { editor } from './content'

/**
 * Питання в редакторі: усі чотири види тримаємо разом, тож перемикання виду туди й назад
 * нічого не губить. На сервер іде лише вид, що обраний (toWire).
 */
export interface EditorQuestion {
  kind: QuestionKind
  prompt: string
  points: number
  explanation: string
  /** single/multiple */
  options: QuestionOption[]
  correct: string[]
  /** text: прийнятні відповіді */
  accepted: string[]
  /** match: пари ліворуч → праворуч і зайві праворуч */
  pairs: { left: QuestionOption; right: QuestionOption }[]
  extras: QuestionOption[]
}

/** id варіантів — короткі ключі: так їх і зберігає сервер (^[A-Za-z0-9_-]{1,16}$). */
export function nextId(prefix: string, used: string[]): string {
  const taken = new Set(used)
  if (prefix === '') {
    for (let i = 0; i < 26; i++) {
      const id = String.fromCharCode(65 + i)
      if (!taken.has(id)) return id
    }
  }
  let n = 1
  while (taken.has(`${prefix || 'O'}${n}`)) n++
  return `${prefix || 'O'}${n}`
}

function emptyPairs(): EditorQuestion['pairs'] {
  return [
    { left: { id: 'L1', text: '' }, right: { id: 'R1', text: '' } },
    { left: { id: 'L2', text: '' }, right: { id: 'R2', text: '' } },
  ]
}

export function newQuestion(): EditorQuestion {
  return {
    kind: 'single',
    prompt: '',
    points: 1,
    explanation: '',
    options: [
      { id: 'A', text: '' },
      { id: 'B', text: '' },
    ],
    correct: [],
    accepted: [],
    pairs: emptyPairs(),
    extras: [],
  }
}

export function fromServer(q: QuestionOut): EditorQuestion {
  const base = newQuestion()
  const draft: EditorQuestion = { ...base, kind: q.kind, prompt: q.prompt, points: q.points, explanation: q.explanation ?? '' }
  const key = q.answer_key
  if (q.kind === 'single' || q.kind === 'multiple') {
    draft.options = q.options.map((o) => ({ ...o }))
    draft.correct = Array.isArray(key) ? [...key] : []
  } else if (q.kind === 'text') {
    draft.accepted = Array.isArray(key) ? [...key] : []
  } else {
    const pairsKey = Array.isArray(key) ? {} : key
    const rights = new Map((q.right_options ?? []).map((r) => [r.id, r]))
    draft.pairs = q.options.map((left) => ({
      left: { ...left },
      right: { ...(rights.get(pairsKey[left.id] ?? '') ?? { id: nextId('R', [...rights.keys()]), text: '' }) },
    }))
    const used = new Set(Object.values(pairsKey))
    draft.extras = (q.right_options ?? []).filter((r) => !used.has(r.id)).map((r) => ({ ...r }))
  }
  return draft
}

const filled = (o: QuestionOption) => o.text.trim() !== ''
const trimOption = (o: QuestionOption): QuestionOption => ({ id: o.id, text: o.text.trim() })

/** Тіло запиту на сервер (порожні варіанти відкидаємо). */
export function toWire(q: EditorQuestion): QuestionFields {
  const common = { kind: q.kind, prompt: q.prompt.trim(), points: q.points, explanation: q.explanation.trim() || null }
  if (q.kind === 'single' || q.kind === 'multiple') {
    const options = q.options.filter(filled).map(trimOption)
    const ids = new Set(options.map((o) => o.id))
    let answer = q.correct.filter((id) => ids.has(id))
    if (q.kind === 'single') answer = answer.slice(0, 1)
    return { ...common, options, right_options: null, answer_key: answer }
  }
  if (q.kind === 'text') {
    return { ...common, options: [], right_options: null, answer_key: q.accepted.map((a) => a.trim()).filter(Boolean) }
  }
  const pairs = q.pairs.filter((p) => filled(p.left) && filled(p.right))
  return {
    ...common,
    options: pairs.map((p) => trimOption(p.left)),
    right_options: [...pairs.map((p) => trimOption(p.right)), ...q.extras.filter(filled).map(trimOption)],
    answer_key: Object.fromEntries(pairs.map((p) => [p.left.id, p.right.id])),
  }
}

/** Однакові для сервера (для автозбереження: порожній новий варіант — ще не зміна). */
export function sameWire(a: EditorQuestion, b: EditorQuestion): boolean {
  return JSON.stringify(toWire(a)) === JSON.stringify(toWire(b))
}

/** Чого бракує, щоб питання можна було зберегти; null — усе гаразд. */
export function missing(q: EditorQuestion): string | null {
  const t = editor.questions
  const wire = toWire(q)
  if (!wire.prompt) return t.needPrompt
  if (q.kind === 'single' || q.kind === 'multiple') {
    if (wire.options.length < 2) return t.needOptions
    if ((wire.answer_key as string[]).length === 0) return t.needCorrect
  } else if (q.kind === 'text') {
    if ((wire.answer_key as string[]).length === 0) return t.needAccepted
  } else if (wire.options.length < 2) {
    return t.needPairs
  }
  return null
}

/** Інший вид відповіді: переносимо, що можна (варіанти ↔ одна правильна). */
export function switchKind(q: EditorQuestion, kind: QuestionKind): EditorQuestion {
  const next = { ...q, kind }
  if (kind === 'single') next.correct = q.correct.slice(0, 1)
  if (kind === 'text' && q.accepted.length === 0 && (q.kind === 'single' || q.kind === 'multiple')) {
    // Правильний варіант стає прийнятною відповіддю: менше набирати заново.
    next.accepted = q.options.filter((o) => q.correct.includes(o.id) && filled(o)).map((o) => o.text.trim())
  }
  return next
}
