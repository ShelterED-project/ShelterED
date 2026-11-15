import { useOutboxCount } from '@/shared/db/useOutboxCount'
import StudentHeader from './sections/StudentHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'
import TodayLessons from './sections/TodayLessons'

export default function LessonsPage() {
  const pending = useOutboxCount()

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="lessons" />
      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader pending={pending} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <TodayLessons />
        </main>
      </div>
      <StudentTabs activeId="lessons" />
    </div>
  )
}
