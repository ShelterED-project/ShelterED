import iconShield from '@/assets/student/header-shield.svg'
import { pluralUk } from '@/shared/lib/plural'
import Brand from '@/shared/ui/Brand'
import { greeting, shelterMode } from '../content'

export default function StudentHeader({ pending }: { pending: number }) {
  const queue =
    pending === 0 ? 'черга порожня' : `${pending} ${pluralUk(pending, ['запис', 'записи', 'записів'])} в черзі`

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-line-soft bg-oil/95 px-5 backdrop-blur-sm md:px-8 xl:h-20 xl:px-10">
      <div className="md:hidden">
        <Brand size="app" />
      </div>
      <div className="hidden md:block">
        <h1 className="font-heading text-2xl leading-[30px] text-parchment xl:text-[28px] xl:leading-[35px]">
          {greeting.title}
        </h1>
        <p className="text-sm text-dim">{greeting.subtitle}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2 md:gap-3">
        {/* TODO: «Режим укриття» й «офлайн» поки статичні; звʼязати зі станом мережі та локального сервера */}
        <div className="flex flex-col items-end">
          <span className="rounded-full bg-line-soft px-3 py-1.5 text-xs font-semibold text-accent">{shelterMode}</span>
          <span role="status" className="text-[11px] leading-[16.5px] text-dim">
            офлайн · {queue}
          </span>
        </div>
        <button
          type="button"
          aria-label="Безпека"
          className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-line focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <img src={iconShield} alt="" width={20} height={20} />
        </button>
      </div>
    </header>
  )
}
