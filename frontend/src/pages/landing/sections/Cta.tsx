import lanternIcon from '@/assets/landing/icon-lantern.svg'
import Button from '@/shared/ui/Button'

export default function Cta() {
  return (
    <section id="about" className="mx-auto max-w-[1152px] px-5 py-16 md:px-8 lg:py-20">
      <div className="flex flex-col items-start gap-6 rounded-[28px] border border-line bg-surface p-6 sm:p-10 lg:flex-row lg:items-center lg:gap-10 lg:p-14">
        <span className="relative flex size-16 shrink-0 items-center justify-center rounded-full bg-accent-soft shadow-[0_0_44px_10px_rgba(242,178,92,0.3)]">
          <img src={lanternIcon} alt="" width={32} height={32} />
        </span>
        <div className="flex-1">
          <h2 className="font-heading text-[22px] leading-[1.3] text-parchment md:text-[28px]">
            Запаліть перший урок у своєму класі
          </h2>
          <p className="mt-2 text-base leading-[26px] text-muted">
            Підключення займає кілька хвилин: вчитель створює клас, учні входять за кодом.
          </p>
        </div>
        <Button to="/register" variant="primary" className="h-14 px-7">
          Зареєструвати школу
        </Button>
      </div>
    </section>
  )
}
