import iconMore from '@/assets/parent/tab-more.svg'
import iconOverview from '@/assets/parent/tab-overview.svg'
import iconAlarms from '@/assets/admin/tab-alarms.svg'
import iconClasses from '@/assets/admin/tab-classes.svg'
import AppTabs from '@/shared/ui/AppTabs'
import { mobileTabs } from '../content'
import type { TabId } from '../content'

const icons: Record<TabId, string> = {
  overview: iconOverview,
  classes: iconClasses,
  alarms: iconAlarms,
  more: iconMore,
}

const items = mobileTabs.map((tab) => ({ ...tab, icon: icons[tab.id] }))

export default function AdminTabs() {
  return <AppTabs items={items} activeId="overview" />
}
