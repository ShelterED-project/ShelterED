import { useEffect, useState } from 'react'
import { CardContent } from '@/features/lessons/CardContent'
import { isAnswered, scoreTest } from '@/features/lessons/grading'
import LessonIntro from '@/features/lessons/LessonIntro'
import QuestionInput from '@/features/lessons/QuestionInput'
import { TestReview } from '@/features/lessons/TestReview'
import { buildSteps } from '@/features/lessons/lessonSteps'
import { review } from '@/features/lessons/content'
import type { CardOut, LessonOut } from '@/features/teacher/lessonEditorApi'
import type { PackLesson } from '@/shared/db/packTypes'
import type { TestAnswers } from '@/shared/db/types'
import { editor } from './content'
import { primaryButton, secondaryButton } from './styles'

const t = editor.preview

/** Урок у формі пакета «Рюкзака» — так його бачить учень (з ключами для розбору). */
function toPack(lesson: LessonOut): PackLesson {
  return {
    id: lesson.id,
    title: lesson.title,
    subject_id: lesson.subject_id,
    main_part: lesson.main_part,
    shelter_part: lesson.shelter_part,
    version: lesson.version,
    modules: lesson.modules.map((m) => ({ ...m, cards: m.cards.map((c) => ({ ...c })) })),
    tests: lesson.tests.map((test) => ({
      id: test.id,
      title: test.title,
      window_enabled: test.window_enabled,
      window_hours: test.window_hours,
      questions: test.questions.map((q) => ({ ...q })),
    })),
  }
}

function text(card: { body: Record<string, unknown> }, key: 'text' | 'caption'): string {
  const value = card.body[key]
  return typeof value === 'string' ? value : ''
}

/**
 * Перегляд уроку очима учня: вступ, модулі картками, тести з розбором. Ті самі компоненти, що
 * в учня, але без подій і прогресу — нічого не зберігається.
 */
export default function LessonPreview({ lesson, onClose }: { lesson: LessonOut; onClose: () => void }) {
  const pack = toPack(lesson)
  const steps = buildSteps(pack, [])
  const cardsById = new Map<string, CardOut>(lesson.modules.flatMap((m) => m.cards.map((c) => [c.id, c] as const)))
  const [stepIndex, setStepIndex] = useState(0)
  const [cardIndex, setCardIndex] = useState(0)
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<TestAnswers>({})
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
    }
  }, [onClose])

  const goStep = (index: number) => {
    setStepIndex(index)
    setCardIndex(0)
    setQuestionIndex(0)
    setAnswers({})
    setReviewing(false)
    document.getElementById('lesson-preview')?.scrollTo({ top: 0 })
  }

  const step = steps[stepIndex]
  const moduleNumber = steps.slice(0, stepIndex + 1).filter((s) => s.kind === 'module').length

  let body
  if (steps.length === 0) {
    body = <p className="text-[15px] text-muted">{t.empty}</p>
  } else if (!step) {
    body = (
      <div className="flex flex-col gap-4">
        <h2 className="font-heading text-2xl text-parchment">{t.done}</h2>
        <p className="text-[15px] text-muted">{t.doneText}</p>
        <div className="flex flex-col gap-3 md:flex-row">
          <button type="button" onClick={() => goStep(0)} className={secondaryButton}>
            {t.restart}
          </button>
          <button type="button" onClick={onClose} className={primaryButton}>
            {t.close}
          </button>
        </div>
      </div>
    )
  } else if (step.kind === 'module') {
    const cards = [...step.module.cards].sort((a, b) => a.position - b.position)
    const card = cards[cardIndex]
    const source = card ? cardsById.get(card.id) : undefined
    const last = cardIndex >= cards.length - 1
    body = (
      <div className="flex flex-col gap-5">
        <p className="text-xs leading-4 font-semibold tracking-[0.96px] text-accent uppercase">
          {t.module(moduleNumber, Math.min(cardIndex + 1, cards.length), cards.length)}
        </p>
        <h2 className="font-heading text-2xl leading-[30px] text-parchment md:text-[32px] md:leading-10">{step.module.title}</h2>
        {stepIndex === 0 && cardIndex === 0 && <LessonIntro text={lesson.shelter_part} />}
        {card ? (
          <CardContent
            key={card.id}
            kind={card.kind}
            text={text(card, 'text')}
            caption={text(card, 'caption')}
            media={{ src: source?.media?.url ?? null, subtitlesSrc: source?.media?.subtitles?.url ?? null }}
          />
        ) : (
          <p className="text-[15px] text-muted">{t.emptyModule}</p>
        )}
        <div className="flex flex-col-reverse gap-3 md:flex-row md:justify-between">
          <button
            type="button"
            disabled={stepIndex === 0 && cardIndex === 0}
            onClick={() => (cardIndex > 0 ? setCardIndex(cardIndex - 1) : goStep(stepIndex - 1))}
            className={secondaryButton}
          >
            {t.back}
          </button>
          <button type="button" onClick={() => (last ? goStep(stepIndex + 1) : setCardIndex(cardIndex + 1))} className={primaryButton}>
            {t.next}
          </button>
        </div>
      </div>
    )
  } else {
    const questions = [...step.test.questions].sort((a, b) => a.position - b.position)
    const question = questions[questionIndex]
    const score = scoreTest(step.test, answers)
    body = reviewing ? (
      <div className="flex flex-col gap-4">
        <h2 className="font-heading text-2xl text-parchment">{step.test.title}</h2>
        {step.test.window_enabled && <p className="rounded-2xl border border-line bg-surface-2 p-3 text-sm text-muted">{t.windowNote}</p>}
        {score && <p className="text-lg font-semibold text-accent">{review.score(score.points, score.max)}</p>}
        <TestReview test={step.test} answers={answers} />
        <button type="button" onClick={() => goStep(stepIndex + 1)} className={`${primaryButton} self-end`}>
          {t.next}
        </button>
      </div>
    ) : (
      question && (
        <div className="flex flex-col gap-4">
          <p className="text-xs leading-4 font-semibold tracking-[0.96px] text-accent uppercase">
            {step.test.title} · {t.question(questionIndex + 1, questions.length)}
          </p>
          <h2 className="text-xl leading-7 font-semibold text-parchment">{question.prompt}</h2>
          <QuestionInput
            key={question.id}
            question={question}
            answer={answers[question.id]}
            onChange={(answer) => setAnswers({ ...answers, [question.id]: answer })}
          />
          <div className="flex flex-col-reverse gap-3 md:flex-row md:justify-between">
            <button
              type="button"
              disabled={questionIndex === 0}
              onClick={() => setQuestionIndex(questionIndex - 1)}
              className={secondaryButton}
            >
              {t.back}
            </button>
            <button
              type="button"
              disabled={!isAnswered(question, answers[question.id])}
              onClick={() => (questionIndex < questions.length - 1 ? setQuestionIndex(questionIndex + 1) : setReviewing(true))}
              className={primaryButton}
            >
              {questionIndex < questions.length - 1 ? t.next : t.finishTest}
            </button>
          </div>
        </div>
      )
    )
  }

  return (
    <div
      id="lesson-preview"
      role="dialog"
      aria-modal="true"
      aria-label={t.title}
      className="fixed inset-0 z-50 overflow-y-auto bg-oil"
    >
      <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-sidebar px-5 py-3 md:px-8">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-parchment">
            {t.title}: {lesson.title}
          </p>
          <p className="text-xs text-dim">{t.note}</p>
        </div>
        <button type="button" onClick={onClose} className={secondaryButton}>
          {t.close}
        </button>
      </header>
      {steps.length > 0 && (
        <div aria-hidden="true" className="mx-auto flex max-w-[760px] gap-1.5 px-5 pt-5">
          {steps.map((s, i) => (
            <span key={s.id} className={`h-1.5 flex-1 rounded-full ${i < stepIndex ? 'bg-accent' : i === stepIndex ? 'bg-accent/50' : 'bg-line-soft'}`} />
          ))}
        </div>
      )}
      <main className="mx-auto max-w-[760px] px-5 py-6">
        <article className="rounded-3xl border border-line bg-surface p-5 md:px-8 md:py-8">{body}</article>
      </main>
    </div>
  )
}
