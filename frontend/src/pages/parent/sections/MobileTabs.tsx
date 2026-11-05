import iconChat from '@/assets/parent/tab-chat.svg'
import iconMore from '@/assets/parent/tab-more.svg'
import iconOverview from '@/assets/parent/tab-overview.svg'
import iconProgress from '@/assets/parent/tab-progress.svg'
import AppTabs from '@/shared/ui/AppTabs'
import { mobileTabs } from '../content'
import type { TabId } from '../content'

const icons: Record<TabId, string> = {
  overview: iconOverview,
  progress: iconProgress,
  chat: iconChat,
  more: iconMore,
}

const items = mobileTabs.map((tab) => ({ ...tab, icon: icons[tab.id] }))

export default function MobileTabs() {
  return <AppTabs items={items} activeId="overview" />
}
