import { Link } from 'react-router'
import arrowIcon from '@/assets/landing/icon-arrow.svg'
import batteryIcon from '@/assets/landing/icon-battery.svg'
import checkIcon from '@/assets/landing/icon-check.svg'
import heroIllustration from '@/assets/landing/hero-illustration.svg'
import lanternIcon from '@/assets/landing/icon-lantern.svg'
import logo from '@/assets/landing/logo.svg'
import mole from '@/assets/landing/mole.svg'
import schoolIcon from '@/assets/landing/icon-school.svg'
import shieldIcon from '@/assets/landing/icon-shield.svg'
import silentIcon from '@/assets/landing/icon-silent.svg'
import studentIcon from '@/assets/landing/icon-student.svg'
import teacherIcon from '@/assets/landing/icon-teacher.svg'
import wifiIcon from '@/assets/landing/icon-wifi.svg'

const btnBase =
  'inline-flex items-center justify-center rounded-[10px] font-sans whitespace-nowrap'
const btnPrimary = `${btnBase} bg-accent font-bold text-oil`
const btnOutline = `${btnBase} border border-line-strong font-semibold text-parchment`

const steps = [
  { title: 'Зранку, поки є світло', text: 'Пакет уроків на день завантажується автоматично.' },
  { title: 'Сирена посеред уроку', text: 'ShelterED знає розклад і відкриває матеріали саме цього уроку.' },
  { title: 'В укритті', text: 'Картки, тести й Кріт-провідник працюють без мережі.' },
  { title: 'Зв’язок повернувся', text: 'Прогрес і перекличка самі летять у хмару — без дублів.' },
]

const roles = [
  {
    icon: studentIcon,
    title: 'Учням',
    text: 'Короткі модулі по 3–5 хвилин, тести без інтернету й Кріт, який пояснює іншими словами.',
    cta: 'Увійти учню',
    to: '/student',
  },
  {
    icon: teacherIcon,
    title: 'Вчителям',
    text: 'Готуйте уроки наперед, запускайте перекличку й бачте прогалини класу.',
    cta: 'Підключити клас',
    to: '/teacher',
  },
  {
    icon: schoolIcon,
    title: 'Адміністрації школи',
    text: 'Скільки дітей в укритті просто зараз, журнал тривог і керування класами.',
    cta: 'Для школи',
    to: '/admin',
  },
]

const safety = [
  { icon: silentIcon, title: 'Тихий режим', text: 'Субтитри на всіх відео, усе можна пройти без звуку.' },
  { icon: batteryIcon, title: 'Береже заряд', text: 'Темна тема й мінімум анімацій за замовчуванням.' },
  { icon: shieldIcon, title: 'Безпека дітей', text: 'Жодної геолокації, мінімум даних, доступ за ролями.' },
  { icon: wifiIcon, title: 'Працює без мережі', text: 'Локальний сервер на ноутбуці вчителя роздає уроки по Wi-Fi.' },
]

const headerLinks = [
  { href: '#how', label: 'Як це працює' },
  { href: '#roles', label: 'Для кого' },
  { href: '#safety', label: 'Безпека' },
  { href: '#about', label: 'Про проєкт' },
]

function Brand({ size }: { size: 'header' | 'footer' }) {
  return (
    <Link to="/" aria-label="ShelterED — на головну" className="flex shrink-0 items-center gap-2 rounded whitespace-nowrap">
      <img src={logo} alt="" width={24} height={24} />
      <span className={`font-heading text-parchment ${size === 'header' ? 'text-lg md:text-2xl' : 'text-lg'}`}>
        ShelterED
      </span>
    </Link>
  )
}

function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-line-soft bg-oil/95 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-[1296px] items-center justify-between gap-3 px-4 md:h-20 md:px-8 xl:px-[72px]">
        <Brand size="header" />
        <nav aria-label="Головна навігація" className="hidden items-center gap-8 lg:flex">
          {headerLinks.map((l) => (
            <a key={l.href} href={l.href} className="text-[15px] text-muted hover:text-parchment">
              {l.label}
            </a>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-2 md:gap-3">
          <Link to="/login" className={`${btnOutline} h-11 px-4 text-[15px] md:px-5`}>
            Увійти
          </Link>
          <Link to="/login" className={`${btnPrimary} hidden h-11 px-5 text-[15px] md:inline-flex`}>
            Зареєструватися
          </Link>
        </div>
      </div>
    </header>
  )
}

function MapPoint({ label, left, top, state }: { label: string; left: string; top: string; state: 'done' | 'unknown' | 'here' }) {
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

function Hero() {
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
          <Link to="/login" className={`${btnPrimary} h-14 px-7`}>
            Почати безкоштовно
          </Link>
          <a href="#how" className={`${btnOutline} h-14 px-7`}>
            Як це працює
          </a>
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

function HowItWorks() {
  return (
    <section id="how" className="border-t border-line-soft">
      <div className="mx-auto max-w-[1296px] px-5 pt-16 pb-12 md:px-8 lg:pt-[85px] lg:pb-20 xl:px-[72px]">
        <p className="text-xs font-bold tracking-[2px] text-accent uppercase">Як це працює</p>
        <h2 className="mt-4 max-w-[720px] font-heading text-[26px] leading-[1.25] text-parchment md:text-[34px]">
          Від ранку до відбою навчання не обривається
        </h2>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <li key={s.title} className="flex flex-col gap-3 rounded-[20px] border border-line bg-surface p-6">
              <span
                className={`relative flex size-10 items-center justify-center rounded-full font-bold ${
                  i === 1 ? 'border-[3px] border-parchment bg-oil text-parchment' : 'bg-accent text-oil'
                }`}
              >
                {i === 1 && <span className="absolute -inset-[3px] rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />}
                <span className="relative">{i + 1}</span>
              </span>
              <h3 className="font-heading text-lg leading-snug text-parchment">{s.title}</h3>
              <p className="text-[15px] leading-6 text-muted">{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function Roles() {
  return (
    <section id="roles" className="mx-auto max-w-[1296px] px-5 pb-16 md:px-8 lg:pb-20 xl:px-[72px]">
      <h2 className="font-heading text-[26px] leading-[1.25] text-parchment md:text-[34px]">
        Один застосунок — кожному своє
      </h2>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {roles.map((r) => (
          <article key={r.title} className="flex flex-col rounded-[20px] border border-line bg-surface-2 p-6">
            <span className="flex size-12 items-center justify-center rounded-xl bg-accent-soft">
              <img src={r.icon} alt="" width={24} height={24} />
            </span>
            <h3 className="mt-5 font-heading text-xl text-parchment">{r.title}</h3>
            <p className="mt-3 flex-1 text-[15px] leading-6 text-muted">{r.text}</p>
            <Link to={r.to} className="mt-6 flex items-center gap-2 rounded text-base font-semibold text-muted hover:text-parchment">
              {r.cta}
              <img src={arrowIcon} alt="" width={16} height={16} />
            </Link>
          </article>
        ))}
      </div>
    </section>
  )
}

function Safety() {
  return (
    <section id="safety" className="border-y border-line-soft bg-surface/40">
      <ul className="mx-auto grid max-w-[1296px] gap-8 px-5 py-12 sm:grid-cols-2 md:px-8 lg:grid-cols-4 lg:py-16 xl:px-[72px]">
        {safety.map((f) => (
          <li key={f.title} className="flex items-start gap-4">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-surface-2">
              <img src={f.icon} alt="" width={20} height={20} />
            </span>
            <div className="flex flex-col gap-[3px]">
              <h3 className="text-base font-bold text-parchment">{f.title}</h3>
              <p className="text-sm leading-[22.75px] text-muted">{f.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Cta() {
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
        <Link to="/login" className={`${btnPrimary} h-14 px-7`}>
          Зареєструвати школу
        </Link>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-line-soft">
      <div className="mx-auto flex max-w-[1296px] flex-col items-start gap-6 px-5 py-10 md:px-8 lg:flex-row lg:items-center lg:justify-between xl:px-[72px]">
        <Brand size="footer" />
        <nav aria-label="Нижня навігація" className="flex flex-wrap gap-x-6 gap-y-3 text-sm text-muted">
          <a href="#how" className="hover:text-parchment">Як це працює</a>
          <span>Приватність</span>
          <span>Екстрена допомога</span>
          <span>Контакти</span>
        </nav>
        <p className="text-xs text-dim">© 2026 ShelterED · SoftServe Garage</p>
      </div>
    </footer>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-oil font-sans text-parchment">
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <Roles />
        <Safety />
        <Cta />
      </main>
      <Footer />
    </div>
  )
}
