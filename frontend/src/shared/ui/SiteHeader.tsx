import Brand from './Brand'
import Button from './Button'

export type NavLink = { href: string; label: string }

export default function SiteHeader({ links }: { links: NavLink[] }) {
  return (
    <header className="sticky top-0 z-10 border-b border-line-soft bg-oil/95 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-[1296px] items-center justify-between gap-3 px-4 md:h-20 md:px-8 xl:px-[72px]">
        <Brand size="header" />
        <nav aria-label="Головна навігація" className="hidden items-center gap-8 lg:flex">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="text-[15px] text-muted hover:text-parchment">
              {l.label}
            </a>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-2 md:gap-3">
          {/* Два входи завжди видно: учні — за кодом класу, дорослі — з поштою. */}
          <Button to="/login" variant="outline" className="h-11 px-3 text-[15px] md:px-5">
            <span className="md:hidden">Дорослі</span>
            <span className="hidden md:inline">Вхід для дорослих</span>
          </Button>
          <Button to="/register" variant="primary" className="h-11 px-3 text-[15px] md:px-5">
            Я учень
          </Button>
        </div>
      </div>
    </header>
  )
}
