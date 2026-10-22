import iconMessages from '@/assets/parent/nav-messages.svg'
import iconNotifications from '@/assets/parent/nav-notifications.svg'
import iconOverview from '@/assets/parent/nav-overview.svg'
import iconProgress from '@/assets/parent/nav-progress.svg'
import iconSettings from '@/assets/parent/nav-settings.svg'
import AppSidebar from '@/shared/ui/AppSidebar'
import { parentUser, sidebarNav } from '../content'
import type { NavId } from '../content'

const icons: Record<NavId, string> = {
  overview: iconOverview,
  progress: iconProgress,
  messages: iconMessages,
  notifications: iconNotifications,
  settings: iconSettings,
}

const items = sidebarNav.map((item) => ({ ...item, icon: icons[item.id] }))

export default function Sidebar() {
  return <AppSidebar items={items} activeId="overview" user={parentUser} />
}
