import iconClock from '@/assets/parent/clock-sm.svg'
import iconLantern from '@/assets/shelter/lantern-dark.svg'
import { useRollCall } from '@/features/roll-call/useRollCall'
import type { RollCallStatus } from '@/features/roll-call/types'
import { checkIn } from '../content'

const STATUS_LABELS: Record<RollCallStatus, string> = {
  shelter: checkIn.shelter,
  safe: checkIn.safe,
}

export default function CheckInCard() {
  const { lastStatus, mark } = useRollCall()

  return (
    <section className="flex flex-col gap-[11.5px] rounded-3xl border border-line bg-surface p-5 xl:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment xl:text-[22px] xl:tracking-[-0.22px]">
          {checkIn.title}
        </h2>
        <p className="text-xs leading-4 text-dim">{checkIn.who}</p>
      </div>
      <p className="text-sm leading-5 text-muted">{checkIn.text}</p>

      <div className="flex flex-col gap-4 py-1">
        <button
          type="button"
          onClick={() => mark('shelter')}
          className="flex h-14 items-center justify-center gap-2 rounded-[10px] bg-accent text-base leading-6 font-bold text-oil shadow-[0_0_24px_5px_rgba(242,178,92,0.35)] focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
        >
          <img src={iconLantern} alt="" width={24} height={24} />
          {checkIn.shelter}
        </button>
        <button
          type="button"
          onClick={() => mark('safe')}
          className="flex h-14 items-center justify-center rounded-[10px] border border-line-strong text-base leading-6 font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {checkIn.safe}
        </button>
      </div>

      {lastStatus && (
        <p role="status" className="text-sm font-semibold text-safe">
          {checkIn.saved}: {STATUS_LABELS[lastStatus]}
        </p>
      )}

      <p className="flex items-center gap-2 text-xs leading-4 text-dim">
        <img src={iconClock} alt="" width={16} height={16} className="shrink-0" />
        {checkIn.note}
      </p>
    </section>
  )
}
