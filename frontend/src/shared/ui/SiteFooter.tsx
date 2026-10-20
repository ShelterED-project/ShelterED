import Brand from './Brand'

export type FooterLink = { label: string; href?: string }

export default function SiteFooter({ links }: { links: FooterLink[] }) {
  return (
    <footer className="border-t border-line-soft">
      <div className="mx-auto flex max-w-[1296px] flex-col items-start gap-6 px-5 py-10 md:px-8 lg:flex-row lg:items-center lg:justify-between xl:px-[72px]">
        <Brand size="footer" />
        <nav aria-label="Нижня навігація" className="flex flex-wrap gap-x-6 gap-y-3 text-sm text-muted">
          {links.map((l) =>
            l.href ? (
              <a key={l.label} href={l.href} className="hover:text-parchment">
                {l.label}
              </a>
            ) : (
              <span key={l.label}>{l.label}</span>
            ),
          )}
        </nav>
        <p className="text-xs text-dim">© 2026 ShelterED · SoftServe Garage</p>
      </div>
    </footer>
  )
}
