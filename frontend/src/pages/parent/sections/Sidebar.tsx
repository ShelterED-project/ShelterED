import iconMessages from '@/assets/parent/nav-messages.svg'
import iconNotifications from '@/assets/parent/nav-notifications.svg'
import iconOverview from '@/assets/parent/nav-overview.svg'
import iconProgress from '@/assets/parent/nav-progress.svg'
import iconSettings from '@/assets/parent/nav-settings.svg'
import Brand from '@/shared/ui/Brand'
import { parentUser, sidebarNav } from '../content'
import type { NavId } from '../content'

const icons: Record<NavId, string> = {
  overview: iconOverview,
  progress: iconProgress,
  messages: iconMessages,
  notifications: iconNotifications,
  settings: iconSettings,
}

const active: NavId = 'overview'

export default function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-[84px] shrink-0 flex-col gap-6 border-r border-line-soft bg-sidebar px-3 py-6 md:flex xl:w-[260px] xl:px-4">
      <div className="flex justify-center px-2 xl:justify-start">
        <Brand size="app" collapsible />
      </div>

      <nav aria-label="Розділи" className="flex flex-col gap-1">
        {/* TODO: підключити маршрути розділів, коли вони зʼявляться */}
        {sidebarNav.map((item) => {
          const isActive = item.id === active
          return (
            <button
              key={item.id}
              type="button"
              aria-current={isActive ? 'page' : undefined}
              className={`flex h-11 items-center justify-center gap-3 rounded-[10px] px-3 text-[15px] focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none xl:justify-start ${
                isActive ? 'bg-surface-2 font-semibold text-accent' : 'text-muted hover:bg-surface'
              }`}
            >
              <img src={icons[item.id]} alt="" width={20} height={20} />
              <span className="sr-only xl:not-sr-only">{item.label}</span>
            </button>
          )
        })}
      </nav>

      <div className="mt-auto flex items-center justify-center gap-3 px-2 xl:justify-start">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-sm font-bold text-parchment">
          {parentUser.initials}
        </div>
        <div className="hidden min-w-0 xl:block">
          <p className="text-sm font-semibold text-parchment">{parentUser.name}</p>
          <p className="text-xs text-dim">{parentUser.role}</p>
        </div>
      </div>
    </aside>
  )
}
