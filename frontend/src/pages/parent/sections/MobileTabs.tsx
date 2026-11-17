import iconChat from '@/assets/parent/tab-chat.svg'
// «Ще» веде в налаштування, тож іконка — шестерня.
import iconMore from '@/assets/parent/tab-settings.svg'
import iconOverview from '@/assets/parent/tab-overview.svg'
import iconProgress from '@/assets/parent/tab-progress.svg'
import AppTabs from '@/shared/ui/AppTabs'
import { mobileTabs, navRoutes } from '../content'
import type { TabId } from '../content'

const icons: Record<TabId, string> = {
  overview: iconOverview,
  progress: iconProgress,
  chat: iconChat,
  more: iconMore,
}

const items = mobileTabs.map((tab) => ({ ...tab, icon: icons[tab.id], to: navRoutes[tab.id] }))

/** activeId null — сторінка поза вкладками (наприклад, налаштування). */
export default function MobileTabs({ activeId = 'overview' }: { activeId?: TabId | null }) {
  return <AppTabs items={items} activeId={activeId ?? ''} />
}
