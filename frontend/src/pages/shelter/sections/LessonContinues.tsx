import iconCheck from '@/assets/landing/icon-check.svg'
import iconArrow from '@/assets/register/icon-arrow-right.svg'
import iconLantern from '@/assets/student/banner-lantern.svg'
import iconDecor from '@/assets/shelter/decor.svg'
import { useShelterLesson } from '@/features/lessons/useShelterLesson'
import { pluralUk } from '@/shared/lib/plural'
import { lesson as texts } from '../content'

type StepState = 'done' | 'current' | 'todo'

function Step({ label, state }: { label: string; state: StepState }) {
  return (
    <li
      aria-current={state === 'current' ? 'step' : undefined}
      className={`flex min-w-0 flex-1 flex-col items-center ${state === 'current' ? 'gap-[5px]' : 'gap-2'}`}
    >
      {state === 'done' && (
        <span className="flex size-8 items-center justify-center rounded-full bg-accent">
          <img src={iconCheck} alt="" width={16} height={16} />
        </span>
      )}
      {state === 'current' && (
        <span className="flex size-[38px] items-center justify-center rounded-full border-[3px] border-parchment bg-oil">
          <span className="size-8 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />
        </span>
      )}
      {state === 'todo' && <span className="size-8 rounded-full border-2 border-line-strong bg-surface" />}
      <span
        className={`max-w-full truncate px-1 text-center text-xs leading-4 ${state === 'current' ? 'font-bold text-parchment' : 'text-dim'}`}
      >
        {label}
      </span>
    </li>
  )
}

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export default function LessonContinues() {
  const { hasPack, lesson, steps, currentStep, progress, lessons } = useShelterLesson()

  const title = lesson?.lesson.title ?? (hasPack ? texts.noLesson : texts.noPack)
  const text = lesson
    ? `${lesson.lesson.modules.length} ${pluralUk(lesson.lesson.modules.length, ['модуль', 'модулі', 'модулів'])} · ${lesson.minutes} хв${currentStep ? '' : ` · ${texts.allDone}`}`
    : hasPack
      ? texts.noLessonText
      : texts.noPackText

  return (
    <section
      aria-labelledby="lesson-title"
      className="relative flex flex-col gap-6 overflow-clip rounded-3xl border border-accent/40 bg-surface-2 p-5 xl:p-8"
    >
      <img src={iconDecor} alt="" width={288} height={288} className="pointer-events-none absolute -top-10 -right-10 size-72" />

      <div className="relative flex items-start gap-4">
        <div className="relative hidden size-14 shrink-0 items-center justify-center rounded-full bg-accent-soft md:flex">
          <span className="absolute inset-0 rounded-full shadow-[0_0_44px_10px_rgba(242,178,92,0.3)]" />
          <img src={iconLantern} alt="" width={28} height={28} className="relative" />
        </div>
        <div className="flex min-w-0 flex-col gap-2 pt-[5.5px]">
          <p className="text-xs leading-4 font-bold tracking-[2px] text-accent uppercase">{texts.eyebrow}</p>
          <h1
            id="lesson-title"
            className="font-heading text-[26px] leading-[29.9px] tracking-[-0.26px] text-parchment xl:pt-[2.5px] xl:text-[40px] xl:leading-[46px] xl:tracking-[-0.4px]"
          >
            {title}
          </h1>
          <p className="text-sm leading-5 text-muted xl:text-[15px]">{text}</p>
        </div>
      </div>

      {steps.length > 0 && (
        <div className="relative flex flex-col gap-4">
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            aria-label="Прогрес уроку"
            className="h-2 rounded-full bg-line-soft"
          >
            <div className="h-2 rounded-full bg-accent" style={{ width: `${progress * 100}%` }} />
          </div>
          <ol className="flex h-14 items-end">
            {steps.map((step) => (
              <Step
                key={step.id}
                label={step.title}
                state={step.done ? 'done' : step.id === currentStep?.id ? 'current' : 'todo'}
              />
            ))}
          </ol>
        </div>
      )}

      <div className="relative flex flex-col gap-3 md:flex-row">
        <button
          type="button"
          onClick={() => scrollTo('task')}
          disabled={!currentStep}
          className="flex h-14 items-center justify-center gap-2 rounded-[10px] bg-accent px-7 text-base font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:opacity-50"
        >
          {texts.resume}
          <img src={iconArrow} alt="" width={20} height={20} />
        </button>
        {lessons.length > 1 && (
          <button
            type="button"
            onClick={() => scrollTo('next-offline')}
            className="h-14 rounded-[10px] border border-line-strong px-6 text-base font-semibold text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {texts.others}
          </button>
        )}
      </div>
    </section>
  )
}
