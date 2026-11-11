import { useState } from 'react'
import mole from '@/assets/landing/mole.svg'
import { completeTest, scoreTest } from '@/features/lessons/completeStep'
import type { PackTest } from '@/shared/db/packTypes'
import { task } from '../content'
import { TaskFrame } from './TaskCard'

const primaryButton =
  'h-12 rounded-[10px] bg-accent px-7 text-[15px] font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:opacity-50'

/**
 * Тест: питання по одному. Для тренувальних є ключ, тож відповідь перевіряється одразу;
 * в оцінюваних тестах ключа немає, їх оцінює сервер після синхронізації.
 */
export default function TestTask({ userId, lessonId, test }: { userId: string; lessonId: string; test: PackTest }) {
  const questions = [...test.questions].sort((a, b) => a.position - b.position)
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string[]>>({})
  const [checked, setChecked] = useState(false)
  const [saving, setSaving] = useState(false)

  const question = questions[index]
  if (!question) return <TaskFrame title={test.title} />

  const selected = answers[question.id] ?? []
  // Оцінюваний тест приходить без ключа (поля немає), тренувальний — з ключем.
  const answerKey = question.answer_key ?? null
  const hasKey = answerKey !== null
  const isLast = index >= questions.length - 1
  const isMultiple = question.kind === 'multiple'
  const isCorrect = answerKey !== null && selected.length === answerKey.length && selected.every((id) => answerKey.includes(id))
  const score = isLast && checked ? scoreTest(test, answers) : null

  const choose = (optionId: string) => {
    if (checked) return
    setAnswers({
      ...answers,
      [question.id]: isMultiple
        ? selected.includes(optionId)
          ? selected.filter((id) => id !== optionId)
          : [...selected, optionId]
        : [optionId],
    })
  }

  const next = async () => {
    if (!isLast) {
      setIndex(index + 1)
      setChecked(false)
      return
    }
    setSaving(true)
    try {
      await completeTest(userId, lessonId, test, answers)
    } finally {
      setSaving(false)
    }
  }

  // Питання без ключа не перевіряємо: одразу «Далі». З ключем спершу «Перевірити».
  const needsCheck = hasKey && !checked

  return (
    <TaskFrame meta={task.testMeta(index + 1, questions.length)} title={question.prompt}>
      <fieldset className="grid gap-3 pt-[9px] md:grid-cols-2">
        <legend className="sr-only">{question.prompt}</legend>
        {isMultiple && <p className="col-span-full text-xs text-dim">{task.multipleHint}</p>}
        {question.options.map((option) => {
          const isSelected = selected.includes(option.id)
          const state = !checked || !hasKey ? '' : answerKey?.includes(option.id) ? 'border-safe' : isSelected ? 'border-accent' : ''
          return (
            <label
              key={option.id}
              className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-[14px] border border-line bg-surface px-4 py-2 text-[17px] leading-[25.5px] font-semibold text-parchment has-checked:border-accent has-checked:bg-surface-2 has-focus-visible:ring-2 has-focus-visible:ring-accent/40 ${state}`}
            >
              <input
                type={isMultiple ? 'checkbox' : 'radio'}
                name={`q-${question.id}`}
                value={option.id}
                checked={isSelected}
                onChange={() => choose(option.id)}
                disabled={checked}
                className={`size-5 shrink-0 appearance-none border border-[#767676] bg-white checked:border-accent checked:bg-[radial-gradient(circle,var(--color-accent)_0_6px,white_6.5px)] ${isMultiple ? 'rounded-md' : 'rounded-full'}`}
              />
              {option.text}
            </label>
          )
        })}
      </fieldset>

      {checked && hasKey && (
        <div className="flex items-end gap-3 pt-[9px]">
          <img src={mole} alt="" width={64} height={64} className="size-16 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]" />
          <p
            role="status"
            className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[19px] leading-[1.25] font-semibold text-parchment md:text-[22px]"
          >
            {isCorrect ? task.correct : task.wrong}
            {score && <span className="block text-base">{task.score(score.points, score.max)}</span>}
          </p>
        </div>
      )}
      {isLast && !hasKey && (
        <p role="status" className="text-sm text-muted">
          {task.testSaved}
        </p>
      )}

      <div className="flex flex-col gap-3 pt-[9px] md:flex-row md:justify-end">
        <button
          type="button"
          onClick={() => (needsCheck ? setChecked(true) : void next())}
          disabled={selected.length === 0 || saving}
          className={primaryButton}
        >
          {needsCheck ? task.check : isLast ? task.finishTest : task.next}
        </button>
      </div>
    </TaskFrame>
  )
}
