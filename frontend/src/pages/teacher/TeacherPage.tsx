import AlertBanner from './sections/AlertBanner'
import GapsCard from './sections/GapsCard'
import Kpis from './sections/Kpis'
import LocalServerCard from './sections/LocalServerCard'
import MobileGreeting from './sections/MobileGreeting'
import RollCallCard from './sections/RollCallCard'
import ScheduleCard from './sections/ScheduleCard'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

export default function TeacherPage() {
  return (
    <div className="flex min-h-screen">
      <TeacherSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting />
          <AlertBanner />
          <Kpis />
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
            <RollCallCard className="xl:min-w-0 xl:flex-1" />
            <div className="flex flex-col gap-5 xl:w-[400px] xl:shrink-0 xl:gap-6">
              <ScheduleCard />
              <GapsCard />
            </div>
          </div>
          <LocalServerCard />
        </main>
      </div>
      <TeacherTabs />
    </div>
  )
}
