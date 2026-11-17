import iconMore from '@/assets/parent/tab-more.svg'
import iconOverview from '@/assets/parent/tab-overview.svg'
import iconAlarms from '@/assets/admin/tab-alarms.svg'
import iconClasses from '@/assets/admin/tab-classes.svg'
import AppTabs from '@/shared/ui/AppTabs'
import { mobileTabs, navRoutes } from '../content'
import type { TabId } from '../content'

const icons: Record<TabId, string> = {
  overview: iconOverview,
  classes: iconClasses,
  alarms: iconAlarms,
  more: iconMore,
}

const items = mobileTabs.map((tab) => ({ ...tab, icon: icons[tab.id], to: navRoutes[tab.id] }))

export default function AdminTabs({ activeId = 'overview' }: { activeId?: TabId }) {
  return <AppTabs items={items} activeId={activeId} />
}
