import iconCalm from '@/assets/student/tab-calm.svg'
import iconLessons from '@/assets/student/tab-lessons.svg'
import iconMe from '@/assets/student/tab-me.svg'
import iconRoute from '@/assets/student/tab-route.svg'
import AppTabs from '@/shared/ui/AppTabs'
import { mobileTabs } from '../content'
import type { TabId } from '../content'

const icons: Record<TabId, string> = {
  route: iconRoute,
  lessons: iconLessons,
  calm: iconCalm,
  me: iconMe,
}

const items = mobileTabs.map((tab) => ({ ...tab, icon: icons[tab.id] }))

export default function StudentTabs() {
  return <AppTabs items={items} activeId="route" />
}
