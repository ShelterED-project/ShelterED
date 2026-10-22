import type { NavItem } from './AppSidebar'

type Props = { items: NavItem[]; activeId: string }

export default function AppTabs({ items, activeId }: Props) {
  return (
    <nav
      aria-label="Розділи"
      className="fixed inset-x-0 bottom-0 flex h-[76px] items-stretch justify-center border-t border-line-soft bg-sidebar px-2 pb-2 md:hidden"
    >
      {/* TODO: підключити маршрути розділів, коли вони зʼявляться */}
      {items.map((tab) => {
        const isActive = tab.id === activeId
        return (
          <button
            key={tab.id}
            type="button"
            aria-current={isActive ? 'page' : undefined}
            className={`flex flex-1 flex-col items-center justify-center gap-[3px] rounded-xl text-[11px] leading-[16.5px] focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
              isActive ? 'font-bold text-accent' : 'text-dim'
            }`}
          >
            <img src={tab.icon} alt="" width={22} height={22} />
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}
