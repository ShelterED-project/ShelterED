import checkIcon from '@/assets/landing/icon-check.svg'
import heroIllustration from '@/assets/landing/hero-illustration.svg'
import mole from '@/assets/landing/mole.svg'
import Button from '@/shared/ui/Button'

type MapPointProps = { label: string; left: string; top: string; state: 'done' | 'unknown' | 'here' }

function MapPoint({ label, left, top, state }: MapPointProps) {
  return (
    <div className="absolute flex items-center gap-2" style={{ left, top }}>
      {state === 'done' && (
        <span className="flex size-10 items-center justify-center rounded-full bg-accent">
          <img src={checkIcon} alt="" width={16} height={16} />
        </span>
      )}
      {state === 'unknown' && <span className="size-10 rounded-full border-2 border-dashed border-muted bg-surface" />}
      {state === 'here' && (
        <span className="flex size-12 items-center justify-center rounded-full border-4 border-parchment bg-oil">
          <span className="size-10 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />
        </span>
      )}
      <span className="flex items-center gap-1 text-sm font-semibold whitespace-nowrap text-parchment">
        {label}
        {state === 'unknown' && (
          <span className="ml-1 rounded-md bg-parchment px-2 py-0.5 text-xs font-semibold text-oil">незвідано</span>
        )}
      </span>
    </div>
  )
}

export default function Hero() {
  return (
    <section className="mx-auto flex max-w-[1296px] flex-col items-stretch gap-12 px-5 pt-12 pb-16 md:px-8 lg:flex-row lg:items-center lg:gap-16 lg:pt-20 lg:pb-24 xl:px-[72px]">
      <div className="flex flex-1 flex-col items-start">
        <p className="flex items-center gap-2 rounded-full border border-line px-3.5 py-2 text-sm text-muted">
          <span className="size-2 rounded-full bg-accent" />
          Працює без інтернету та світла
        </p>
        <h1 className="mt-6 font-heading text-[32px] leading-[1.2] tracking-[-0.5px] text-parchment md:text-[44px] xl:text-[48px]">
          Пропущена тема — не провал, а незвідана ділянка.
        </h1>
        <p className="mt-5 max-w-[560px] text-[17px] leading-7 text-muted md:text-[19px]">
          ShelterED перетворює час в укритті на тихе й безпечне навчання. Урок продовжується навіть тоді, коли зникли
          світло і зв’язок, — а Кріт із ліхтариком веде маршрутом тем.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button to="/register" variant="primary" className="h-14 px-7">
            Почати безкоштовно
          </Button>
          <Button href="#how" variant="outline" className="h-14 px-7">
            Як це працює
          </Button>
        </div>
      </div>

      <div className="relative aspect-[520/540] w-full max-w-[520px] self-center overflow-hidden rounded-[28px] border border-line bg-surface lg:shrink-0 lg:basis-[520px]">
        <img src={heroIllustration} alt="" className="absolute inset-0 size-full max-w-none" />
        <span className="absolute top-5 left-5 rounded-full bg-line-soft px-3 py-1.5 text-xs font-bold text-accent">
          Режим укриття · офлайн
        </span>
        <MapPoint label="Натуральні числа" left="8.16%" top="57.97%" state="done" />
        <MapPoint label="Дроби" left="22.11%" top="42.03%" state="done" />
        <MapPoint label="Десяткові" left="46.01%" top="28.08%" state="unknown" />
        <MapPoint label="Відсотки · ти тут" left="36.05%" top="13.14%" state="here" />
        <div className="absolute right-4 bottom-4 left-4 flex items-end gap-3">
          <img src={mole} alt="Кріт — маскот ShelterED" width={96} height={96} className="size-16 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)] sm:size-24" />
          <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-xl leading-[1.25] font-semibold text-parchment sm:text-[22px]">
            Пропустили «Десяткові»? Повернімось разом — я поруч.
          </p>
        </div>
      </div>
    </section>
  )
}
