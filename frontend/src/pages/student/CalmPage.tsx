import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'
import { useWellbeing } from '@/features/wellbeing/useWellbeing'
import { weatherIcon } from '@/features/wellbeing/weather'
import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { calmPage } from './content'
import Breathing from './sections/Breathing'
import type { BreathingHandle } from './sections/Breathing'
import MoodCheckIn from './sections/MoodCheckIn'
import StudentHeader from './sections/StudentHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'

/** День школи (YYYY-MM-DD) як «пт». Полудень UTC: день не зсувається поясом. */
function weekday(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString('uk-UA', { weekday: 'short' })
}

/**
 * «Спокій»: «Як ти зараз?», дихальна вправа й свої картинки за останні дні.
 * Не тест і не діагноз: жодних чисел про дитину, усе добровільно, працює офлайн.
 */
export default function CalmPage() {
  const pending = useOutboxCount()
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

  const labels = new Map((texts?.child.scale ?? []).map((s) => [s.picture, s.label]))

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="calm" />
      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader pending={pending} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <div className="flex flex-col gap-1">
            <h1 className="font-heading text-2xl leading-[30px] text-parchment">{calmPage.title}</h1>
            <p className="text-sm text-dim">{calmPage.subtitle}</p>
          </div>

          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
            <div className="flex flex-col gap-5 xl:min-w-0 xl:flex-1 xl:gap-6">
              {texts ? (
                <MoodCheckIn
                  texts={texts}
                  answeredToday={answeredToday}
                  showSupport={self?.show_support ?? false}
                  onAnswer={answer}
                  onBreathe={breathe}
                />
              ) : (
                <p className="rounded-[22px] border border-line bg-surface p-5 text-sm text-muted">
                  {calmPage.offlineNoTexts}
                </p>
              )}

              {texts && (
                <section className="flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 md:p-6">
                  <h2 className="font-heading text-xl leading-7 text-parchment">{texts.child.history_title}</h2>
                  {self && self.days.length > 0 ? (
                    <ol className="flex flex-wrap gap-2">
                      {self.days.map((day) => (
                        <li
                          key={day.date}
                          className="flex w-14 flex-col items-center gap-1 rounded-2xl bg-surface-2 py-2"
                          aria-label={`${weekday(day.date)}: ${labels.get(day.picture) ?? ''}`}
                        >
                          <span className="text-2xl" aria-hidden="true">
                            {weatherIcon[day.picture]}
                          </span>
                          <span className="text-xs text-dim" aria-hidden="true">
                            {weekday(day.date)}
                          </span>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="text-sm text-muted">{calmPage.history.empty}</p>
                  )}
                </section>
              )}
            </div>

            <div className="xl:w-[400px] xl:shrink-0">
              <Breathing ref={breathing} />
            </div>
          </div>
        </main>
      </div>
      <StudentTabs activeId="calm" />
    </div>
  )
}
