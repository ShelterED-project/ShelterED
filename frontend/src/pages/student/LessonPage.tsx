import { useOutboxCount } from '@/shared/db/useOutboxCount'
import AlertNotice from './sections/AlertNotice'
import { LessonOutline, LessonQueue } from './sections/LessonOutline'
import LessonPlayer from './sections/LessonPlayer'
import PageHeader, { MobileTitle } from './sections/PageHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'
import { useLessonTitle } from './sections/useLessonTitle'

/**
 * Урок у звичайному режимі (без тривоги): картки модуля по одній, план уроку й черга відправки.
 * Дані ті самі, що в режимі укриття (урок з ?lesson=, усе з пакета на пристрої), але без переклички.
 * Якщо тривога почнеться, AlertWatcher перенесе учня в /shelter з цим самим уроком.
 */
export default function LessonPage() {
  const pending = useOutboxCount()
  const { title, subtitle } = useLessonTitle()

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="lessons" />
      <div className="flex min-w-0 flex-1 flex-col">
        <PageHeader title={title} subtitle={subtitle} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:px-10 xl:py-8">
          <AlertNotice />
          <MobileTitle title={title} subtitle={subtitle} />
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px] xl:items-start xl:gap-6">
            <div className="flex min-w-0 flex-col gap-5">
              <LessonPlayer />
            </div>
            <aside className="flex flex-col gap-5">
              <LessonOutline />
              <LessonQueue pending={pending} />
            </aside>
          </div>
        </main>
      </div>
      <StudentTabs activeId="lessons" />
    </div>
  )
}
