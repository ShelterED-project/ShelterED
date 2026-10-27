import iconNotifications from '@/assets/parent/nav-notifications.svg'
import iconOverview from '@/assets/parent/nav-overview.svg'
import iconSettings from '@/assets/parent/nav-settings.svg'
import iconClasses from '@/assets/admin/nav-classes.svg'
import iconServers from '@/assets/admin/nav-servers.svg'
import iconUsers from '@/assets/admin/nav-users.svg'
import AppSidebar from '@/shared/ui/AppSidebar'
import { adminUser, sidebarNav } from '../content'
import type { NavId } from '../content'

const icons: Record<NavId, string> = {
  overview: iconOverview,
  classes: iconClasses,
  users: iconUsers,
  alarms: iconNotifications,
  servers: iconServers,
  settings: iconSettings,
}

const items = sidebarNav.map((item) => ({ ...item, icon: icons[item.id] }))

export default function AdminSidebar() {
  return <AppSidebar items={items} activeId="overview" user={adminUser} />
}
