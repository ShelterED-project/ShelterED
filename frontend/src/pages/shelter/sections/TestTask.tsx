import { useState } from 'react'
import { completeTest } from '@/features/lessons/completeStep'
import { isAnswered } from '@/features/lessons/grading'
import QuestionInput from '@/features/lessons/QuestionInput'
import type { PackTest } from '@/shared/db/packTypes'
import type { TestAnswers } from '@/shared/db/types'
import { task } from '../content'
import { TaskFrame } from './TaskCard'

const primaryButton =
  'h-14 rounded-[10px] bg-accent px-7 text-base font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:opacity-50 md:h-12 md:text-[15px]'
const outlineButton =
  'h-14 rounded-[10px] border border-line-strong px-6 text-base font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none md:h-12 md:text-[15px]'

/**
 * Тест: питання по одному (варіанти, текст або відповідність). Відповіді й подія test_attempt
 * пишуться разом, коли учень завершує тест. Тренувальний тест (з ключем) після цього показує
 * розбір: onFinished отримує відповіді. Оцінюваний (без ключа) оцінює сервер після синхронізації.
 */
export default function TestTask({
  userId,
  lessonId,
  test,
  onFinished,
}: {
  userId: string
  lessonId: string
  test: PackTest
  /** Після збереження тренувального тесту: показати розбір */
  onFinished?: (answers: TestAnswers) => void
}) {
  const questions = [...test.questions].sort((a, b) => a.position - b.position)
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<TestAnswers>({})
  const [saving, setSaving] = useState(false)

  const question = questions[index]
  if (!question) return <TaskFrame title={test.title} />

  const answer = answers[question.id]
  const answered = isAnswered(question, answer)
  const isLast = index >= questions.length - 1
  // Оцінюваний тест приходить без ключа (поля немає), тренувальний — з ключем.
  const hasKey = test.questions.every((q) => q.answer_key != null)

  const next = async () => {
    if (!answered || saving) return
    if (!isLast) {
      setIndex(index + 1)
      return
    }
    setSaving(true)
    try {
      await completeTest(userId, lessonId, test, answers)
      if (hasKey) onFinished?.(answers)
    } finally {
      setSaving(false)
    }
  }

  return (
    <TaskFrame meta={task.testMeta(index + 1, questions.length)} title={question.prompt}>
      {/* key: нове питання — свіже поле (фокус, прокрутка кнопок відповідності). */}
      <QuestionInput
        key={question.id}
        question={question}
        answer={answer}
        onChange={(value) => setAnswers({ ...answers, [question.id]: value })}
        onSubmit={() => void next()}
        disabled={saving}
      />

      {isLast && !hasKey && (
        <p role="status" className="text-sm text-muted">
          {task.testSaved}
        </p>
      )}

      {/* На телефоні «Далі» над «Назад»: головна дія ближче до відповіді. */}
      <div className="flex flex-col-reverse gap-3 pt-[9px] md:flex-row md:justify-end">
        {index > 0 && (
          <button type="button" onClick={() => setIndex(index - 1)} disabled={saving} className={outlineButton}>
            {task.back}
          </button>
        )}
        <button type="button" onClick={() => void next()} disabled={!answered || saving} className={primaryButton}>
          {isLast ? task.finishTest : task.next}
        </button>
      </div>
    </TaskFrame>
  )
}
