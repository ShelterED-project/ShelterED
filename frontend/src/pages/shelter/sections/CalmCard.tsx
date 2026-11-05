import iconChevron from '@/assets/shelter/chevron.svg'
import iconPin from '@/assets/shelter/pin.svg'
import { calm } from '../content'

export default function CalmCard() {
  return (
    <section className="flex items-center gap-5 rounded-3xl border border-line bg-surface p-5 xl:p-6">
      <div className="relative flex size-20 shrink-0 items-center justify-center rounded-full bg-accent-soft">
        <span className="absolute inset-3 rounded-full border border-accent/40" />
        <img src={iconPin} alt="" width={28} height={28} className="relative" />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 pb-px">
        <h2 className="font-heading text-lg leading-7 tracking-[-0.18px] text-parchment">{calm.title}</h2>
        <p className="text-xs leading-4 text-dim">{calm.text}</p>
        {/* TODO: запускати вправу з диханням, коли зʼявиться відповідна сторінка */}
        <button
          type="button"
          className="flex items-center gap-1 self-start rounded pt-[3.5px] text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {calm.start}
          <img src={iconChevron} alt="" width={16} height={16} />
        </button>
      </div>
    </section>
  )
}
