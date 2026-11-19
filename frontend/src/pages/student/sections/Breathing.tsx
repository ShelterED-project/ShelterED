import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import iconLantern from '@/assets/student/banner-lantern.svg'
import iconPause from '@/assets/student/calm-pause.svg'
import { calmPage } from '../content'

type Phase = 'inhale' | 'hold' | 'exhale'

/** Ритм вправи: вдих 4 · пауза 4 · видих 6 секунд. */
const PHASES: { phase: Phase; seconds: number }[] = [
  { phase: 'inhale', seconds: 4 },
  { phase: 'hold', seconds: 4 },
  { phase: 'exhale', seconds: 6 },
]
const CYCLE = PHASES.reduce((sum, p) => sum + p.seconds, 0)

function phaseAt(elapsed: number): { phase: Phase; seconds: number; secondsLeft: number } {
  let t = elapsed % CYCLE
  for (const p of PHASES) {
    if (t < p.seconds) return { phase: p.phase, seconds: p.seconds, secondsLeft: p.seconds - t }
    t -= p.seconds
  }
  return { phase: 'inhale', seconds: PHASES[0].seconds, secondsLeft: PHASES[0].seconds }
}

export interface BreathingHandle {
  start: () => void
}

/**
 * «Хвилинка спокою»: дихання разом з колом. Без звуку (тихий режим). Таймер працює лише під
 * час вправи (енергоменеджер); з «зменшити рух» коло не анімується, лишаються підписи й лічильник.
 */
const Breathing = forwardRef<BreathingHandle>(function Breathing(_props, ref) {
  const t = calmPage.breathing
  const [minutes, setMinutes] = useState(2)
  const [elapsed, setElapsed] = useState<number | null>(null)
  const [paused, setPaused] = useState(false)
  const total = minutes * 60
  const started = elapsed !== null
  const finished = started && elapsed >= total
  const running = started && !finished && !paused

  useImperativeHandle(
    ref,
    () => ({
      start: () => {
        setElapsed(0)
        setPaused(false)
      },
    }),
    [],
  )

  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setElapsed((e) => (e === null ? null : e + 1)), 1000)
    return () => clearInterval(id)
  }, [running])

  const { phase, seconds, secondsLeft } = phaseAt(elapsed ?? 0)
  // Коло: на вдиху росте, на паузі тримає розмір, на видиху зменшується.
  const big = running && (phase === 'inhale' || phase === 'hold')
  const duration = running ? (phase === 'exhale' ? 6 : 4) : 0.3
  const active = started && !finished

  const toggle = () => {
    if (!started || finished) {
      setElapsed(0)
      setPaused(false)
    } else setPaused(!paused)
  }

  return (
    <section
      id="breathing"
      aria-labelledby="breathing-title"
      className="flex flex-col items-center rounded-[28px] border border-accent/40 bg-surface-2 px-5 pt-7 pb-8 text-center md:pt-10 md:pb-12"
    >
      <h2 id="breathing-title" className="text-xs leading-4 font-semibold tracking-[0.96px] text-accent uppercase">
        {t.title}
      </h2>

      <div className="relative my-8 flex size-56 items-center justify-center md:size-64" aria-hidden="true">
        <span className="absolute inset-0 rounded-full border border-accent/20" />
        <span className="absolute inset-6 rounded-full border border-accent/30" />
        <span
          className={`absolute inset-12 rounded-full bg-accent-soft shadow-[0_0_44px_10px_rgba(242,178,92,0.3)] motion-safe:transition-transform motion-safe:ease-in-out ${
            active && !big ? 'scale-75' : 'scale-100'
          }`}
          style={{ transitionDuration: `${duration}s` }}
        />
        <img src={iconLantern} alt="" width={56} height={56} className="relative" />
      </div>

      <div role="status" aria-live="polite" className="flex min-h-[72px] flex-col items-center justify-center gap-2">
        {active ? (
          <>
            <span className="font-heading text-[32px] leading-10 tracking-[-0.4px] text-parchment md:text-[40px]">
              {t.phases[phase]}
            </span>
            <span className="text-base leading-6 text-muted">
              {Array.from({ length: seconds }, (_, i) => seconds - i).map((n, i) => (
                <span key={n} className={n === secondsLeft ? 'font-semibold text-parchment' : undefined}>
                  {i > 0 && ' · '}
                  {n}
                </span>
              ))}
            </span>
          </>
        ) : (
          <span className="max-w-[360px] text-base leading-6 text-muted">{finished ? t.done : t.hint}</span>
        )}
      </div>

      <div className="mt-6 flex w-full flex-col items-center gap-3 md:w-auto md:flex-row">
        <button
          type="button"
          onClick={toggle}
          className="flex h-14 w-full items-center justify-center gap-2 rounded-[10px] bg-accent px-7 text-base leading-6 font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none md:w-auto"
        >
          {running && <img src={iconPause} alt="" width={20} height={20} />}
          {running ? t.pause : paused && !finished ? t.resume : finished ? t.again : t.start}
        </button>
        <div
          role="group"
          aria-label={t.durationLabel}
          className="flex self-stretch rounded-xl border border-line bg-surface p-1"
        >
          {t.durations.map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={minutes === m}
              onClick={() => {
                // Нова тривалість — вправа з початку.
                setMinutes(m)
                setElapsed(null)
                setPaused(false)
              }}
              className={`h-9 flex-1 rounded-lg px-4 text-sm leading-5 font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none md:flex-none ${
                minutes === m ? 'bg-surface-2 text-accent ring-1 ring-line-strong ring-inset' : 'text-muted'
              }`}
            >
              {t.duration(m)}
            </button>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs leading-4 text-dim">
        {active ? `${t.left(total - (elapsed ?? 0))} · ${t.note}` : t.note}
      </p>
    </section>
  )
})

export default Breathing
