import iconLantern from '@/assets/admin/alert-lantern.svg'
import { alertBanner } from '../content'

export default function AlertBanner() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-accent/40 bg-surface-2 p-5 md:flex-row md:items-center">
      <div className="relative flex size-12 shrink-0 items-center justify-center rounded-full bg-accent-soft">
        <span className="absolute inset-0 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />
        <img src={iconLantern} alt="" width={24} height={24} className="relative" />
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="text-[17px] leading-[25.5px] font-semibold text-parchment">{alertBanner.title}</h2>
        <p className="text-sm leading-5 text-muted">{alertBanner.text}</p>
      </div>
      {/* TODO: відкривати журнал тривог, коли зʼявиться відповідна сторінка */}
      <button
        type="button"
        className="h-12 shrink-0 rounded-[10px] border border-line-strong px-5 text-[15px] font-semibold whitespace-nowrap text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        {alertBanner.journal}
      </button>
    </section>
  )
}
