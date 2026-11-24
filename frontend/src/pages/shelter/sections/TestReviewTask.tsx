import mole from '@/assets/landing/mole.svg'
import { scoreTest } from '@/features/lessons/grading'
import { TestReview } from '@/features/lessons/TestReview'
import { review } from '@/features/lessons/content'
import type { PackTest } from '@/shared/db/packTypes'
import type { TestAnswers } from '@/shared/db/types'
import { task } from '../content'
import { TaskFrame } from './TaskCard'

/**
 * Розбір тренувального тесту одразу після здачі: бали, кожне питання (правильно чи ні,
 * правильна відповідь, пояснення). Спроба вже збережена, тож «Далі» лише веде до наступного кроку.
 */
export default function TestReviewTask({
  test,
  answers,
  onContinue,
}: {
  test: PackTest
  answers: TestAnswers
  onContinue: () => void
}) {
  const score = scoreTest(test, answers)
  const mood = !score ? review.good : score.points === score.max ? review.great : score.points > 0 ? review.good : review.try

  return (
    <TaskFrame meta={task.reviewMeta} title={test.title}>
      <div className="flex items-end gap-3 pt-[9px]">
        <img src={mole} alt="" width={64} height={64} className="size-16 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]" />
        <p
          role="status"
          className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[19px] leading-[1.25] font-semibold text-parchment md:text-[22px]"
        >
          {mood}
          {score && <span className="block text-base">{review.score(score.points, score.max)}</span>}
        </p>
      </div>
      <TestReview test={test} answers={answers} />
      <div className="flex flex-col gap-3 pt-[9px] md:flex-row md:justify-end">
        <button
          type="button"
          onClick={onContinue}
          className="h-14 rounded-[10px] bg-accent px-7 text-base font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none md:h-12 md:text-[15px]"
        >
          {review.continue}
        </button>
      </div>
    </TaskFrame>
  )
}
