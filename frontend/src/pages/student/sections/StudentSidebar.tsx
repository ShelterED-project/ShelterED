import iconSettings from '@/assets/parent/nav-settings.svg'
import iconCalm from '@/assets/student/nav-calm.svg'
import iconLessons from '@/assets/student/nav-lessons.svg'
import iconMe from '@/assets/student/nav-me.svg'
import iconRoute from '@/assets/student/nav-route.svg'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import AppSidebar from '@/shared/ui/AppSidebar'
import { navRoutes, sidebarNav, studentRole } from '../content'
import type { NavId } from '../content'

const icons: Record<NavId, string> = {
  route: iconRoute,
  lessons: iconLessons,
  calm: iconCalm,
  me: iconMe,
  settings: iconSettings,
}

const items = sidebarNav.map((item) => ({ ...item, icon: icons[item.id], to: navRoutes[item.id] }))

export default function StudentSidebar({ activeId = 'route' }: { activeId?: NavId }) {
  const user = useCurrentUser()
  return (
    <AppSidebar
      items={items}
      activeId={activeId}
      user={{ initials: user?.initials ?? '', name: user?.fullName ?? '', role: studentRole }}
    />
  )
}
