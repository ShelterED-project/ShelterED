import mole from '@/assets/landing/mole.svg'
import Brand from '@/shared/ui/Brand'
import Button from '@/shared/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col bg-oil font-sans text-parchment">
      <header className="border-b border-line-soft">
        <div className="mx-auto flex h-16 max-w-[1296px] items-center px-4 md:h-20 md:px-8 xl:px-[72px]">
          <Brand size="header" />
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-5 py-12 md:px-8">
        <div className="flex w-full max-w-[560px] flex-col items-center text-center">
          <img
            src={mole}
            alt="Кріт — маскот ShelterED"
            width={160}
            height={160}
            className="size-32 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)] md:size-40"
          />
          <p className="mt-6 text-xs font-bold tracking-[2px] text-accent uppercase">Помилка 404</p>
          <h1 className="mt-2 font-heading text-[32px] leading-[1.15] text-parchment md:text-[48px]">
            Сторінку не знайдено
          </h1>
          <p className="mt-3 text-[15px] leading-6 text-muted md:text-[17px]">
            Можливо, посилання застаріло або в адресі є помилка. Повернімось на знайомий маршрут.
          </p>
          <p className="mt-6 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-5 py-3 font-mole text-[22px] leading-tight font-semibold text-parchment md:text-[26px]">
            Тут темно, навіть мій ліхтарик не допомагає.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Button to="/" variant="primary" className="h-14 px-7">
              На головну
            </Button>
            <Button to="/login" variant="outline" className="h-14 px-7">
              Увійти
            </Button>
          </div>
        </div>
      </main>
    </div>
  )
}
