import AlertBanner from './sections/AlertBanner'
import Kpis from './sections/Kpis'
import RollCallCard from './sections/RollCallCard'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

/** Перекличка класу: керування (старт, закриття, відбій), підсумки й статус кожного учня. */
export default function RollCallPage() {
  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="rollcall" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <AlertBanner />
          <Kpis />
          <RollCallCard />
        </main>
      </div>
      <TeacherTabs activeId="rollcall" />
    </div>
  )
}
