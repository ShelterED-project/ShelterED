import iconClock from '@/assets/parent/clock-sm.svg'
import iconShield from '@/assets/parent/shield-check.svg'
import { safetyStatus } from '../content'

export default function SafetyStatus() {
  return (
    <section
      aria-labelledby="safety-title"
      className="flex flex-col gap-4 overflow-clip rounded-[22px] border border-safe/40 bg-surface-2 p-5 md:flex-row md:items-center md:gap-6 md:p-6"
    >
      <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-safe/15">
        <img src={iconShield} alt="" width={28} height={28} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 pt-[5.5px] md:pt-0">
        <p className="text-xs font-bold tracking-[1.5px] text-accent uppercase">{safetyStatus.alert}</p>
        <h2
          id="safety-title"
          className="pt-[1.5px] font-heading text-[22px] leading-[27.5px] tracking-[-0.22px] text-parchment md:text-[26px] md:leading-[32.5px] md:tracking-[-0.26px]"
        >
          {safetyStatus.title}
        </h2>
        <p className="text-sm leading-5 text-muted">{safetyStatus.text}</p>
      </div>
      <div className="flex flex-col gap-1 md:items-end md:text-right">
        <p className="flex items-center gap-1.5 text-xs text-dim">
          <img src={iconClock} alt="" width={16} height={16} />
          {safetyStatus.dataTime}
        </p>
        <p className="max-w-[260px] text-xs text-dim">{safetyStatus.note}</p>
      </div>
    </section>
  )
}
