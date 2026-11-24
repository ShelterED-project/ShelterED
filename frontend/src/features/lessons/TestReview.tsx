import type { PackQuestion, PackTest } from '@/shared/db/packTypes'
import type { QuestionAnswer, TestAnswers } from '@/shared/db/types'
import { review as texts } from './content'
import { answerText, keyText } from './answers'
import { isCorrect } from './grading'

function Lines({ label, lines, tone }: { label: string; lines: string[]; tone: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-xs leading-4 text-dim">{label}</p>
      {lines.length === 0 ? (
        <p className="text-[15px] leading-[22.5px] text-dim">{texts.none}</p>
      ) : (
        lines.map((line, i) => (
          <p key={i} className={`text-[15px] leading-[22.5px] font-semibold ${tone}`}>
            {line}
          </p>
        ))
      )}
    </div>
  )
}

/** Розбір одного питання: правильно чи ні, відповідь учня, правильна відповідь і пояснення. */
export function QuestionReview({
  question,
  answer,
  number,
}: {
  question: PackQuestion
  answer: QuestionAnswer | undefined
  number: number
}) {
  const correct = isCorrect(question, answer) === true
  return (
    <li
      className={`flex flex-col gap-3 rounded-[18px] border bg-surface-2 p-4 ${correct ? 'border-safe/50' : 'border-accent/50'}`}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs leading-4 text-dim">{texts.question(number)}</p>
        <p className={`shrink-0 text-sm font-bold ${correct ? 'text-safe' : 'text-accent'}`}>
          {correct ? `✓ ${texts.correct}` : `✗ ${texts.wrong}`}
        </p>
      </div>
      <p className="text-[17px] leading-[25.5px] font-semibold text-parchment">{question.prompt}</p>
      <Lines label={texts.yours} lines={answerText(question, answer)} tone={correct ? 'text-safe' : 'text-muted'} />
      {!correct && <Lines label={texts.right} lines={keyText(question)} tone="text-safe" />}
      {question.explanation && (
        <div className="flex flex-col gap-0.5 border-t border-line-soft pt-3">
          <p className="text-xs leading-4 text-dim">{texts.why}</p>
          <p className="text-[15px] leading-[22.5px] text-parchment">{question.explanation}</p>
        </div>
      )}
    </li>
  )
}

/** Розбір тренувального тесту: усі питання по порядку. Працює лише з ключем відповідей. */
export function TestReview({ test, answers }: { test: PackTest; answers: TestAnswers }) {
  const questions = [...test.questions].sort((a, b) => a.position - b.position)
  return (
    <ol className="flex flex-col gap-3">
      {questions.map((q, i) => (
        <QuestionReview key={q.id} question={q} answer={answers[q.id]} number={i + 1} />
      ))}
    </ol>
  )
}
