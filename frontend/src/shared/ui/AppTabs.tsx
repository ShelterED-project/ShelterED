import { Link } from 'react-router'
import type { NavItem } from './AppSidebar'
import NavIcon from './NavIcon'

type Props = { items: NavItem[]; activeId: string }

export default function AppTabs({ items, activeId }: Props) {
  return (
    <nav
      aria-label="Розділи"
      className="fixed inset-x-0 bottom-0 flex h-[76px] items-stretch justify-center border-t border-line-soft bg-sidebar px-2 pb-2 md:hidden"
    >
      {items.map((tab) => {
        const isActive = tab.id === activeId
        const className = `flex flex-1 flex-col items-center justify-center gap-[3px] rounded-xl text-[11px] leading-[16.5px] focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
          isActive ? 'font-bold text-accent' : 'text-dim'
        }`
        const content = (
          <>
            <NavIcon src={tab.icon} size={22} />
            {tab.label}
          </>
        )
        return tab.to ? (
          <Link key={tab.id} to={tab.to} aria-current={isActive ? 'page' : undefined} className={className}>
            {content}
          </Link>
        ) : (
          <button key={tab.id} type="button" aria-current={isActive ? 'page' : undefined} className={className}>
            {content}
          </button>
        )
      })}
    </nav>
  )
}
