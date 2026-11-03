import iconOverview from '@/assets/parent/nav-overview.svg'
import iconUsers from '@/assets/admin/nav-users.svg'
import iconLessons from '@/assets/student/nav-lessons.svg'
import iconMap from '@/assets/teacher/nav-map.svg'
import iconSchedule from '@/assets/teacher/nav-schedule.svg'
import iconSettings from '@/assets/teacher/nav-settings.svg'
import iconSync from '@/assets/teacher/nav-sync.svg'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import AppSidebar from '@/shared/ui/AppSidebar'
import { sidebarNav, teacherRole } from '../content'
import type { NavId } from '../content'

const icons: Record<NavId, string> = {
  overview: iconOverview,
  rollcall: iconUsers,
  lessons: iconLessons,
  schedule: iconSchedule,
  map: iconMap,
  sync: iconSync,
  settings: iconSettings,
}

const items = sidebarNav.map((item) => ({ ...item, icon: icons[item.id] }))

export default function TeacherSidebar() {
  const user = useCurrentUser()
  return (
    <AppSidebar
      items={items}
      activeId="overview"
      user={{ initials: user?.initials ?? '', name: user?.fullName ?? '', role: teacherRole }}
    />
  )
}
