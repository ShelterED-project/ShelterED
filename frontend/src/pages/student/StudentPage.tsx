import { useOutboxCount } from '@/shared/db/useOutboxCount'
import CalmCard from './sections/CalmCard'
import CheckIn from './sections/CheckIn'
import LessonBanner from './sections/LessonBanner'
import MobileGreeting from './sections/MobileGreeting'
import RouteSection from './sections/RouteSection'
import StudentHeader from './sections/StudentHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'
import SyncStatus from './sections/SyncStatus'
import TodayLessons from './sections/TodayLessons'

export default function StudentPage() {
  const pending = useOutboxCount()

  return (
    <div className="flex min-h-screen">
      <StudentSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader pending={pending} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting />
          <LessonBanner />
          <div className="flex flex-col gap-5 xl:flex-row xl:gap-6">
            <RouteSection className="xl:min-w-0 xl:flex-1" />
            <div className="flex flex-col gap-5 xl:w-[380px] xl:shrink-0 xl:gap-6">
              <CheckIn />
              <SyncStatus pending={pending} />
              <CalmCard />
            </div>
          </div>
          <TodayLessons />
        </main>
      </div>
      <StudentTabs />
    </div>
  )
}
