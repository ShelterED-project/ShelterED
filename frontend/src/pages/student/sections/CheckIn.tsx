import iconClock from '@/assets/parent/clock-sm.svg'
import { useRollCall } from '@/features/roll-call/useRollCall'
import type { RollCallStatus } from '@/features/roll-call/types'
import { checkIn } from '../content'

const STATUS_LABELS: Record<RollCallStatus, string> = {
  shelter: checkIn.shelter,
  safe: checkIn.safe,
}

export default function CheckIn() {
  const { lastStatus, mark } = useRollCall()

  return (
    <section className="flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
      <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{checkIn.title}</h2>
      <p className="text-sm leading-5 text-muted">{checkIn.text}</p>

      <button
        type="button"
        onClick={() => mark('shelter')}
        className="h-14 rounded-[10px] bg-accent text-base font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
      >
        {checkIn.shelter}
      </button>
      <button
        type="button"
        onClick={() => mark('safe')}
        className="h-14 rounded-[10px] border border-line-strong text-base font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        {checkIn.safe}
      </button>

      {lastStatus && (
        <p role="status" className="text-sm font-semibold text-safe">
          {checkIn.saved}: {STATUS_LABELS[lastStatus]}
        </p>
      )}

      <p className="flex items-start gap-2 text-xs text-dim">
        <img src={iconClock} alt="" width={16} height={16} className="mt-0 shrink-0" />
        {checkIn.offlineNote}
      </p>
    </section>
  )
}
