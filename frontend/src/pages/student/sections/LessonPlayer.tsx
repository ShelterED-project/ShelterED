import { useState } from 'react'
import { Link } from 'react-router'
import iconArrowRight from '@/assets/register/icon-arrow-right.svg'
import iconBook from '@/assets/student/book.svg'
import iconArrowLeft from '@/assets/student/lesson-arrow-left.svg'
import iconVideo from '@/assets/student/lesson-video.svg'
import { useAppSelector } from '@/app/hooks'
import { completeModule } from '@/features/lessons/completeStep'
import type { LessonStep } from '@/features/lessons/lessonSteps'
import { useShelterLesson } from '@/features/lessons/useShelterLesson'
import { TaskFrame } from '@/pages/shelter/sections/TaskCard'
import TestResults from '@/pages/shelter/sections/TestResults'
import TestTask from '@/pages/shelter/sections/TestTask'
import { task } from '@/pages/shelter/content'
import type { PackCard, PackModule } from '@/shared/db/packTypes'
import { lessonPage as texts, navRoutes } from '../content'

const buttonBase =
  'flex h-14 items-center justify-center gap-2 rounded-[10px] text-base leading-6 focus-visible:outline-none disabled:opacity-50'
const outlineButton = `${buttonBase} border border-line-strong px-6 font-semibold text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40`
const primaryButton = `${buttonBase} bg-accent px-7 font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60`

function cardText(card: PackCard, field: 'text' | 'caption'): string {
  const value = card.body[field]
  return typeof value === 'string' ? value : ''
}

/** Що буде далі: наступна картка модуля, а на останній — наступний крок уроку. */
function NextPreview({ meta, title, video }: { meta: string; title: string; video: boolean }) {
  return (
    <div className="flex items-center gap-4 rounded-[18px] border border-line bg-surface p-4">
      <span className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-surface-2">
        <img src={video ? iconVideo : iconBook} alt="" width={video ? 24 : 20} height={video ? 24 : 20} />
      </span>
      <div className="flex min-w-0 flex-col">
        <p className="text-xs leading-4 text-dim">{meta}</p>
        <p className="truncate text-[15px] leading-[22.5px] font-semibold text-parchment">{title}</p>
      </div>
    </div>
  )
}

function ModulePlayer({
  userId,
  lessonId,
  module,
  number,
  nextStep,
}: {
  userId: string
  lessonId: string
  module: PackModule
  /** Номер модуля в уроці, з 1 */
  number: number
  nextStep: LessonStep | null
}) {
  const cards = [...module.cards].sort((a, b) => a.position - b.position)
  const [index, setIndex] = useState(0)
  const [saving, setSaving] = useState(false)

  const card = cards[index]
  const isLast = index >= cards.length - 1
  const nextCard = cards[index + 1]

  const advance = async () => {
    if (!isLast) {
      setIndex(index + 1)
      return
    }
    // Модуль пройдено: подія module_progress і локальний прогрес в одній транзакції.
    setSaving(true)
    try {
      await completeModule(userId, lessonId, module.id)
    } finally {
      setSaving(false)
    }
  }

  const kind = card ? (texts.kinds[card.kind] ?? card.kind) : ''
  const text = card ? cardText(card, 'text') : ''
  const caption = card ? cardText(card, 'caption') : ''

  return (
    <>
      {cards.length > 0 && (
        <div className="flex items-center gap-4">
          <p className="text-sm leading-5 font-semibold whitespace-nowrap text-parchment">
            {texts.progress(number, index + 1, cards.length)}
          </p>
          <div aria-hidden="true" className="flex flex-1 gap-1.5">
            {cards.map((c, i) => (
              <span
                key={c.id}
                className={`h-1.5 flex-1 rounded-full ${i < index ? 'bg-accent' : i === index ? 'bg-accent/50' : 'bg-line-soft'}`}
              />
            ))}
          </div>
          <p className="hidden text-xs leading-4 whitespace-nowrap text-dim md:block">{texts.minutes(module.duration_min)}</p>
        </div>
      )}

      <article
        id="task"
        aria-labelledby="task-title"
        className="flex flex-col rounded-3xl border border-line bg-surface p-5 md:px-8 md:pt-9 md:pb-8"
      >
        {card && (
          <p className="text-xs leading-4 font-semibold tracking-[0.96px] text-accent uppercase">
            {texts.cardEyebrow(index + 1, kind)}
          </p>
        )}
        <h2
          id="task-title"
          className="mt-2.5 font-heading text-2xl leading-[30px] tracking-[-0.24px] text-parchment md:text-[32px] md:leading-10 md:tracking-[-0.32px]"
        >
          {module.title}
        </h2>
        {text && <p className="mt-4 max-w-[680px] text-lg leading-7 whitespace-pre-line text-muted">{text}</p>}
        {card && card.kind !== 'text' && (
          <div className="mt-4 rounded-2xl border border-line bg-surface-2 p-5">
            {caption && <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">{caption}</p>}
            <p className="text-sm leading-5 text-dim">{texts.mediaPending}</p>
          </div>
        )}
      </article>

      {nextCard ? (
        <NextPreview
          meta={texts.nextCard(index + 2)}
          // У картки немає заголовка: підпис медіа або початок тексту (обрізається в один рядок).
          title={cardText(nextCard, 'caption') || cardText(nextCard, 'text') || (texts.kinds[nextCard.kind] ?? nextCard.kind)}
          video={nextCard.kind === 'video'}
        />
      ) : (
        nextStep && <NextPreview meta={texts.nextStep} title={nextStep.title} video={false} />
      )}

      {/* На телефоні «Далі» над «Назад»: головна дія ближче до вмісту. */}
      <div className="flex flex-col-reverse gap-3 md:flex-row md:justify-between">
        {index > 0 ? (
          <button type="button" onClick={() => setIndex(index - 1)} className={outlineButton}>
            <img src={iconArrowLeft} alt="" width={20} height={20} />
            {texts.back}
          </button>
        ) : (
          <Link to={navRoutes.lessons ?? '/student/lessons'} className={outlineButton}>
            <img src={iconArrowLeft} alt="" width={20} height={20} />
            {texts.back}
          </Link>
        )}
        <button type="button" onClick={() => void advance()} disabled={saving} className={primaryButton}>
          {texts.next}
          <img src={iconArrowRight} alt="" width={20} height={20} />
        </button>
      </div>
    </>
  )
}

/** Головна колонка уроку: поточний модуль картками або тест; після всіх кроків — результати. */
export default function LessonPlayer() {
  const { lesson, steps, currentStep, records } = useShelterLesson()
  const userId = useAppSelector((s) => s.auth.session?.user.id)

  if (!lesson || !userId) return <TaskFrame title={task.empty} />
  if (!currentStep) {
    return (
      <TaskFrame title={task.allDone}>
        <TestResults steps={steps} records={records} />
      </TaskFrame>
    )
  }
  if (currentStep.kind === 'test') {
    return <TestTask key={currentStep.id} userId={userId} lessonId={lesson.lesson.id} test={currentStep.test} />
  }

  const moduleSteps = steps.filter((step) => step.kind === 'module')
  const nextStep = steps[steps.indexOf(currentStep) + 1] ?? null
  // key: новий модуль починається з першої картки.
  return (
    <ModulePlayer
      key={currentStep.id}
      userId={userId}
      lessonId={lesson.lesson.id}
      module={currentStep.module}
      number={moduleSteps.indexOf(currentStep) + 1}
      nextStep={nextStep}
    />
  )
}
