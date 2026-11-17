import { useOutboxCount } from '@/shared/db/useOutboxCount'
import LessonContinues from '@/pages/shelter/sections/LessonContinues'
import NextOffline from '@/pages/shelter/sections/NextOffline'
import TaskCard from '@/pages/shelter/sections/TaskCard'
import AlertNotice from './sections/AlertNotice'
import StudentHeader from './sections/StudentHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'

/**
 * Урок у звичайному режимі (без тривоги): той самий програвач, що й у режимі укриття
 * (урок з ?lesson=, усе з пакета на пристрої), але без переклички й рядка тривоги.
 * Якщо тривога почнеться, AlertWatcher перенесе учня в /shelter з цим самим уроком.
 */
export default function LessonPage() {
  const pending = useOutboxCount()

  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="lessons" />
      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader pending={pending} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <AlertNotice />
          {/* Одна колонка: «Інші уроки» розкладають картки в 3 стовпці, тож їм потрібна вся ширина. */}
          <LessonContinues />
          <TaskCard />
          <NextOffline />
        </main>
      </div>
      <StudentTabs activeId="lessons" />
    </div>
  )
}
