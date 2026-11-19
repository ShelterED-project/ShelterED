import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'
import mole from '@/assets/landing/mole.svg'
import iconBreathing from '@/assets/student/calm-breathing.svg'
import { useWellbeing } from '@/features/wellbeing/useWellbeing'
import { calmPage } from './content'
import Breathing from './sections/Breathing'
import type { BreathingHandle } from './sections/Breathing'
import MoodCheckIn from './sections/MoodCheckIn'
import PageHeader, { MobileTitle } from './sections/PageHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'

/**
 * «Спокій»: дихальна вправа, «Як ти зараз?» зі своїми картинками за 14 днів і вправи.
 * Не тест і не діагноз: жодних чисел про дитину, усе добровільно, працює офлайн.
 */
export default function CalmPage() {
  const { texts, self, answeredToday, answer } = useWellbeing()
  const breathing = useRef<BreathingHandle>(null)
  const { hash } = useLocation()

  // Перехід з картки «Хвилинка спокою» (#breathing): одразу показати вправу.
  useEffect(() => {
    if (hash === '#breathing') document.getElementById('breathing')?.scrollIntoView({ block: 'center' })
  }, [hash])

  const breathe = () => {
    document.getElementById('breathing')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    breathing.current?.start()
  }

  const exercise = calmPage.exercises.breathing

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="calm" />
      <div className="flex min-w-0 flex-1 flex-col">
        <PageHeader title={calmPage.title} subtitle={calmPage.subtitle} />
        <main className="flex flex-col gap-6 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:px-10 xl:py-8">
          <MobileTitle title={calmPage.title} subtitle={calmPage.subtitle} />

          <div className="flex flex-col gap-6 xl:flex-row xl:items-start">
            <div className="min-w-0 xl:flex-1">
              <Breathing ref={breathing} />
            </div>

            <div className="flex flex-col gap-6 xl:w-[400px] xl:shrink-0">
              {texts ? (
                <MoodCheckIn
                  texts={texts}
                  answeredToday={answeredToday}
                  showSupport={self?.show_support ?? false}
                  days={self?.days ?? null}
                  onAnswer={answer}
                  onBreathe={breathe}
                />
              ) : (
                <p className="rounded-[22px] border border-line bg-surface p-5 text-sm text-muted">
                  {calmPage.offlineNoTexts}
                </p>
              )}

              <div className="flex items-end gap-3">
                <img
                  src={mole}
                  alt=""
                  width={80}
                  height={80}
                  className="size-20 shrink-0 drop-shadow-[0_0_14px_rgba(242,178,92,0.35)]"
                />
                <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[22px] leading-[27.5px] text-parchment">
                  {calmPage.mole}
                </p>
              </div>
            </div>
          </div>

          <section aria-labelledby="exercises-title" className="flex flex-col gap-4">
            <h2 id="exercises-title" className="font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">
              {calmPage.exercises.title}
            </h2>
            <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <li>
                <button
                  type="button"
                  onClick={breathe}
                  className="flex h-full w-full flex-col items-start gap-3 rounded-[20px] border border-line bg-surface p-5 text-left hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
                >
                  <span className="flex size-12 items-center justify-center rounded-xl bg-accent-soft">
                    <img src={iconBreathing} alt="" width={24} height={24} />
                  </span>
                  <span className="font-heading text-lg leading-[22.5px] tracking-[-0.18px] text-parchment">
                    {exercise.title}
                  </span>
                  <span className="text-sm leading-5 text-muted">{exercise.text}</span>
                  <span className="pt-[22.5px] text-xs leading-4 text-dim">{exercise.meta}</span>
                </button>
              </li>
            </ul>
          </section>
        </main>
      </div>
      <StudentTabs activeId="calm" />
    </div>
  )
}
