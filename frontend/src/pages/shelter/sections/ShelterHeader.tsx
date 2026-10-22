import iconBattery from '@/assets/shelter/battery.svg'
import iconHelp from '@/assets/shelter/help-shield.svg'
import Brand from '@/shared/ui/Brand'
import { header } from '../content'

const chip = 'flex items-center gap-1.5 rounded-full bg-line-soft px-3 py-1.5 text-xs font-bold whitespace-nowrap text-accent'

export default function ShelterHeader({ pending }: { pending: number }) {
  return (
    <header className="border-b border-line-soft bg-oil">
      <div className="mx-auto flex h-16 max-w-[1296px] items-center justify-between gap-3 px-5 md:px-8 xl:h-20 xl:px-10">
        <div className="flex items-center gap-3">
          <Brand size="app" />
          <span className="hidden rounded-full border border-accent/50 px-3 py-1.5 text-xs font-bold whitespace-nowrap text-accent md:block">
            {header.quiet}
          </span>
        </div>
        <div className="flex items-center gap-2 md:gap-3">
          {/* TODO: «Офлайн» і заряд поки статичні; звʼязати зі станом мережі та пристрою */}
          <div className="flex items-center gap-2">
            <span className={chip}>
              <span className="size-1.5 rounded-full bg-accent" />
              {header.offline}
            </span>
            <span className={`${chip} hidden md:flex`}>
              <span className="size-1.5 rounded-full bg-accent" />
              {pending} в черзі
            </span>
          </div>
          <p className="hidden items-center gap-1.5 text-xs text-dim md:flex">
            <img src={iconBattery} alt="" width={20} height={20} />
            {header.battery}
          </p>
          {/* TODO: підключити виклик допомоги, коли зʼявиться відповідний сценарій */}
          <button
            type="button"
            aria-label={header.help}
            className="flex h-11 items-center gap-2 rounded-xl bg-sos px-3 text-sm font-bold text-white focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none md:px-4"
          >
            <img src={iconHelp} alt="" width={20} height={20} />
            <span className="hidden md:inline">{header.help}</span>
          </button>
        </div>
      </div>
    </header>
  )
}
