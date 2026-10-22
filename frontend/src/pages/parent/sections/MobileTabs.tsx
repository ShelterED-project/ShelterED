import iconChat from '@/assets/parent/tab-chat.svg'
import iconMore from '@/assets/parent/tab-more.svg'
import iconOverview from '@/assets/parent/tab-overview.svg'
import iconProgress from '@/assets/parent/tab-progress.svg'
import { mobileTabs } from '../content'
import type { TabId } from '../content'

const icons: Record<TabId, string> = {
  overview: iconOverview,
  progress: iconProgress,
  chat: iconChat,
  more: iconMore,
}

const active: TabId = 'overview'

export default function MobileTabs() {
  return (
    <nav
      aria-label="Розділи"
      className="fixed inset-x-0 bottom-0 flex h-[76px] items-stretch justify-center border-t border-line-soft bg-sidebar px-2 pb-2 md:hidden"
    >
      {/* TODO: підключити маршрути розділів, коли вони зʼявляться */}
      {mobileTabs.map((tab) => {
        const isActive = tab.id === active
        return (
          <button
            key={tab.id}
            type="button"
            aria-current={isActive ? 'page' : undefined}
            className={`flex flex-1 flex-col items-center justify-center gap-[3px] rounded-xl text-[11px] leading-[16.5px] focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
              isActive ? 'font-bold text-accent' : 'text-dim'
            }`}
          >
            <img src={icons[tab.id]} alt="" width={22} height={22} />
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}
