import iconSettings from '@/assets/parent/nav-settings.svg'
import iconCalm from '@/assets/student/nav-calm.svg'
import iconLessons from '@/assets/student/nav-lessons.svg'
import iconMe from '@/assets/student/nav-me.svg'
import iconRoute from '@/assets/student/nav-route.svg'
import AppSidebar from '@/shared/ui/AppSidebar'
import { sidebarNav, studentUser } from '../content'
import type { NavId } from '../content'

const icons: Record<NavId, string> = {
  route: iconRoute,
  lessons: iconLessons,
  calm: iconCalm,
  me: iconMe,
  settings: iconSettings,
}

const items = sidebarNav.map((item) => ({ ...item, icon: icons[item.id] }))

export default function StudentSidebar() {
  return <AppSidebar items={items} activeId="route" user={studentUser} />
}
