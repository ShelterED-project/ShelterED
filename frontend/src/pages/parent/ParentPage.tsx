import { useState } from 'react'
import type { ChildId } from './content'
import Homework from './sections/Homework'
import Kpis from './sections/Kpis'
import MobileGreeting from './sections/MobileGreeting'
import MobileHeader from './sections/MobileHeader'
import MobileTabs from './sections/MobileTabs'
import RollCallLog from './sections/RollCallLog'
import SafetyStatus from './sections/SafetyStatus'
import Sidebar from './sections/Sidebar'
import TeacherMessage from './sections/TeacherMessage'
import TopBar from './sections/TopBar'
import Visibility from './sections/Visibility'
import WeekChart from './sections/WeekChart'

export default function ParentPage() {
  // TODO: дані дашборда поки однакові для обох дітей; розділити, коли зʼявиться API
  const [childId, setChildId] = useState<ChildId>('olya')

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        <TopBar childId={childId} onChange={setChildId} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:gap-6 md:px-10 md:py-8">
          <MobileGreeting childId={childId} onChange={setChildId} />
          <SafetyStatus />
          <Kpis />
          <div className="flex flex-col gap-5 md:gap-6 xl:flex-row">
            <WeekChart className="xl:flex-1" />
            <Homework className="xl:w-[400px] xl:shrink-0" />
          </div>
          <div className="flex flex-col gap-5 md:gap-6 xl:flex-row">
            <RollCallLog className="xl:min-w-0 xl:flex-1" />
            <div className="flex flex-col gap-5 md:gap-6 xl:w-[400px] xl:shrink-0">
              <TeacherMessage />
              <Visibility />
            </div>
          </div>
        </main>
      </div>
      <MobileTabs />
    </div>
  )
}
