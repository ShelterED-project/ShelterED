import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import { calmPage } from '../content'

type Phase = 'inhale' | 'hold' | 'exhale'

/** Ритм вправи: вдих 4 · пауза 4 · видих 6 секунд, разом 2 хвилини. */
const PHASES: { phase: Phase; seconds: number }[] = [
  { phase: 'inhale', seconds: 4 },
  { phase: 'hold', seconds: 4 },
  { phase: 'exhale', seconds: 6 },
]
const CYCLE = PHASES.reduce((sum, p) => sum + p.seconds, 0)
const TOTAL = 120

function phaseAt(elapsed: number): { phase: Phase; secondsLeft: number } {
  let t = elapsed % CYCLE
  for (const p of PHASES) {
    if (t < p.seconds) return { phase: p.phase, secondsLeft: p.seconds - t }
    t -= p.seconds
  }
  return { phase: 'inhale', secondsLeft: PHASES[0].seconds }
}

export interface BreathingHandle {
  start: () => void
}

/**
 * «Хвилинка спокою»: дихання разом з кругом. Без звуку (тихий режим). Таймер працює лише під
 * час вправи; з «зменшити рух» круг не анімується, лишаються підписи й лічильник.
 */
const Breathing = forwardRef<BreathingHandle>(function Breathing(_props, ref) {
  const t = calmPage.breathing
  const [elapsed, setElapsed] = useState<number | null>(null)
  const running = elapsed !== null && elapsed < TOTAL
  const finished = elapsed !== null && elapsed >= TOTAL

  useImperativeHandle(ref, () => ({ start: () => setElapsed(0) }), [])

  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setElapsed((e) => (e === null ? null : e + 1)), 1000)
    return () => clearInterval(id)
  }, [running])

  const { phase, secondsLeft } = phaseAt(elapsed ?? 0)
  // Круг: на вдиху росте, на паузі тримає розмір, на видиху зменшується.
  const big = running && (phase === 'inhale' || phase === 'hold')
  const duration = running ? (phase === 'exhale' ? 6 : 4) : 0.3

  return (
    <section id="breathing" className="flex flex-col items-center gap-5 rounded-[22px] border border-line bg-surface p-5 text-center md:p-6">
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.title}</h2>
        <p className="text-sm text-dim">{t.text}</p>
      </div>

      <div className="relative flex size-56 items-center justify-center" aria-hidden="true">
        <span className="absolute inset-0 rounded-full border border-accent/20" />
        <span
          className={`absolute inset-0 rounded-full bg-accent-soft shadow-[0_0_40px_6px_rgba(242,178,92,0.18)] motion-safe:transition-transform motion-safe:ease-in-out ${
            big ? 'scale-100' : 'scale-50'
          }`}
          style={{ transitionDuration: `${duration}s` }}
        />
      </div>

      <p role="status" aria-live="polite" className="min-h-14">
        {running ? (
          <>
            <span className="block font-heading text-2xl text-parchment">{t.phases[phase]}</span>
            <span className="block text-sm text-muted">
              {secondsLeft} · {t.left(TOTAL - (elapsed ?? 0))}
            </span>
          </>
        ) : (
          <span className="block text-sm text-muted">{finished ? t.done : t.hint}</span>
        )}
      </p>

      <button
        type="button"
        onClick={() => setElapsed(running ? null : 0)}
        className={`h-12 rounded-[10px] px-8 text-[15px] font-semibold focus-visible:ring-2 focus-visible:outline-none ${
          running
            ? 'border border-line-strong text-parchment hover:bg-surface-2 focus-visible:ring-accent/40'
            : 'bg-accent text-oil focus-visible:ring-parchment/60'
        }`}
      >
        {running ? t.stop : finished ? t.again : t.start}
      </button>
    </section>
  )
})

export default Breathing
