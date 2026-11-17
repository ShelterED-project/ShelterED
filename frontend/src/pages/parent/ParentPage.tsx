import iconMessages from '@/assets/parent/nav-messages.svg'
import iconProgress from '@/assets/parent/nav-progress.svg'
import { useChildDashboard } from '@/features/parent/useChildDashboard'
import { useParentChildren } from '@/features/parent/useParentChildren'
import ComingSoonCard from '@/shared/ui/ComingSoonCard'
import { loading, offline, rollCallLog, teacherMessage } from './content'
import Homework from './sections/Homework'
import Kpis from './sections/Kpis'
import LinkChild from './sections/LinkChild'
import MobileGreeting from './sections/MobileGreeting'
import MobileHeader from './sections/MobileHeader'
import MobileTabs from './sections/MobileTabs'
import SafetyStatus from './sections/SafetyStatus'
import Sidebar from './sections/Sidebar'
import TopBar from './sections/TopBar'
import Visibility from './sections/Visibility'
import WeekChart from './sections/WeekChart'

export default function ParentPage() {
  const { children, selected, select, isLoading, isOffline: childrenOffline } = useParentChildren()
  const dashboard = useChildDashboard(selected?.child_id ?? null)
  const noChildren = !isLoading && children.length === 0

  return (
    <div className="flex min-h-screen">
      <Sidebar activeId="overview" />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        <TopBar childList={children} selected={selected} onChange={select} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:gap-6 md:px-10 md:py-8">
          <MobileGreeting childList={children} selected={selected} onChange={select} />

          {isLoading && (
            <p role="status" className="text-sm text-muted">
              {loading}
            </p>
          )}
          {(childrenOffline || (selected && dashboard.isOffline)) && (
            <p role="status" className="text-sm text-muted">
              {offline}
            </p>
          )}

          {noChildren && <LinkChild empty onLinked={select} />}

          {selected && (
            <>
              <SafetyStatus
                name={selected.display_name}
                alert={dashboard.alert}
                rollCall={dashboard.rollCall}
                updatedAt={dashboard.rollCallUpdatedAt}
                isOffline={dashboard.isOffline}
              />
              <Kpis progress={dashboard.progress} knowledgeMap={dashboard.knowledgeMap} />
              <div className="flex flex-col gap-5 md:gap-6 xl:flex-row">
                <WeekChart progress={dashboard.progress} className="xl:flex-1" />
                <Homework
                  progress={dashboard.progress}
                  knowledgeMap={dashboard.knowledgeMap}
                  className="xl:w-[400px] xl:shrink-0"
                />
              </div>
              <div className="flex flex-col gap-5 md:gap-6 xl:flex-row">
                <div className="flex flex-col gap-5 md:gap-6 xl:min-w-0 xl:flex-1">
                  <ComingSoonCard title={rollCallLog.title} soon={rollCallLog.soon} text={rollCallLog.text} icon={iconProgress} />
                  <ComingSoonCard
                    title={teacherMessage.title}
                    soon={teacherMessage.soon}
                    text={teacherMessage.text}
                    icon={iconMessages}
                  />
                  <LinkChild onLinked={select} />
                </div>
                <Visibility className="xl:w-[400px] xl:shrink-0" />
              </div>
            </>
          )}
        </main>
      </div>
      <MobileTabs activeId="overview" />
    </div>
  )
}
