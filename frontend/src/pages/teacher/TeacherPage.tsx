import AlertBanner from './sections/AlertBanner'
import GapsCard from './sections/GapsCard'
import Kpis from './sections/Kpis'
import MobileGreeting from './sections/MobileGreeting'
import ScheduleCard from './sections/ScheduleCard'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

/**
 * Огляд вчителя: лише найважливіше. Тривога й перекличка (підсумок), уроки на сьогодні, прогалини.
 * Деталі — на окремих сторінках: перекличка, розклад, мапа класу.
 */
export default function TeacherPage() {
  return (
    <div className="flex min-h-screen">
      <TeacherSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting />
          <AlertBanner />
          <Kpis linkToRollCall />
          <div className="grid gap-5 xl:grid-cols-2 xl:items-start xl:gap-6">
            <ScheduleCard />
            <GapsCard />
          </div>
        </main>
      </div>
      <TeacherTabs />
    </div>
  )
}
