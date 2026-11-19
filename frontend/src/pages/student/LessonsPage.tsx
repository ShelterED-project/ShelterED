import { todayLabel } from '@/shared/lib/date'
import PageHeader, { MobileTitle } from './sections/PageHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'
import TodayLessons from './sections/TodayLessons'
import { todayLessons as t } from './content'

export default function LessonsPage() {
  // Назву класу дасть API; поки підпис — лише дата.
  const subtitle = todayLabel({ capitalize: true })

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="lessons" />
      <div className="flex min-w-0 flex-1 flex-col">
        <PageHeader title={t.title} subtitle={subtitle} />
        <main className="flex flex-col gap-6 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:px-10 xl:py-8">
          <MobileTitle title={t.title} subtitle={subtitle} />
          <TodayLessons />
        </main>
      </div>
      <StudentTabs activeId="lessons" />
    </div>
  )
}
