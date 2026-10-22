import { useOutboxStats } from '@/shared/db/useOutboxStats'
import AlertStrip from './sections/AlertStrip'
import CalmCard from './sections/CalmCard'
import CheckInCard from './sections/CheckInCard'
import Connection from './sections/Connection'
import LessonContinues from './sections/LessonContinues'
import NextOffline from './sections/NextOffline'
import ShelterHeader from './sections/ShelterHeader'
import TaskCard from './sections/TaskCard'
import Tips from './sections/Tips'

export default function ShelterModePage() {
  const stats = useOutboxStats()

  return (
    <div className="min-h-screen">
      <AlertStrip />
      <ShelterHeader pending={stats.total} />
      <main className="mx-auto max-w-[1296px] px-5 pt-6 pb-[100px] md:px-8 xl:px-10 xl:py-8">
        {/* До xl колонки «розкриваються» (contents), а order задає послідовність:
            перекличка, потім урок, потім зв’язок і поради. На xl — дві незалежні колонки. */}
        <div className="flex flex-col gap-5 md:gap-6 xl:flex-row">
          <div className="contents xl:flex xl:min-w-0 xl:flex-1 xl:flex-col xl:gap-6">
            <div className="order-2 xl:order-none">
              <LessonContinues />
            </div>
            <div className="order-2 xl:order-none">
              <TaskCard />
            </div>
            <div className="order-2 xl:order-none">
              <NextOffline />
            </div>
          </div>
          <div className="contents xl:flex xl:w-[400px] xl:shrink-0 xl:flex-col xl:gap-6">
            <div className="order-1 xl:order-none">
              <CheckInCard />
            </div>
            <div className="order-3 xl:order-none">
              <Connection stats={stats} />
            </div>
            <div className="order-3 xl:order-none">
              <CalmCard />
            </div>
            <div className="order-3 xl:order-none">
              <Tips />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
