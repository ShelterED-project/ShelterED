import { useState } from 'react'
import { Link } from 'react-router'
import { alertMinutes, useSchoolOverview } from '@/features/admin/useSchoolOverview'
import { alarms, loading, navRoutes, offline } from './content'
import AdminHeader from './sections/AdminHeader'
import AdminSidebar from './sections/AdminSidebar'
import AdminTabs from './sections/AdminTabs'
import AlarmLog from './sections/AlarmLog'
import AlertBanner from './sections/AlertBanner'
import ClassesCard from './sections/ClassesCard'
import CreateUserDialog from './sections/CreateUserDialog'
import Kpis from './sections/Kpis'
import MobileGreeting from './sections/MobileGreeting'
import UsersCard from './sections/UsersCard'

/** Скільки тривог на огляді; решта — у журналі. */
const RECENT = 5

export default function AdminPage() {
  const [creating, setCreating] = useState(false)
  const school = useSchoolOverview()
  const classNames = new Map(school.classes.map((c) => [c.id, c.name]))

  return (
    <div className="flex min-h-screen">
      <AdminSidebar activeId="overview" />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader onAddUser={() => setCreating(true)} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting />
          {school.isLoading && (
            <p role="status" className="text-sm text-muted">
              {loading}
            </p>
          )}
          {school.isOffline && (
            <p role="status" className="text-sm text-muted">
              {offline}
            </p>
          )}
          <AlertBanner
            alert={school.alert}
            marked={school.shelter.inShelter + school.shelter.safe}
            total={school.shelter.total}
          />
          <Kpis
            shelter={school.shelter}
            hasRollCall={school.hasRollCall}
            classes={school.classes.length}
            teachers={school.teachers.length}
            alarms={school.weekAlerts.length}
            alarmMinutes={school.weekAlerts.reduce((sum, a) => sum + alertMinutes(a), 0)}
          />
          <div className="flex flex-col gap-5 xl:flex-row xl:gap-6">
            <ClassesCard classes={school.classes} rollCalls={school.rollCalls} className="xl:min-w-0 xl:flex-1" />
            <UsersCard
              teachers={school.teachers}
              classes={school.classes}
              className="xl:w-[400px] xl:shrink-0"
              onInvite={() => setCreating(true)}
            />
          </div>
          <AlarmLog
            alerts={school.weekAlerts.slice(0, RECENT)}
            classNames={classNames}
            title={alarms.recent}
            actions={
              <Link
                to={navRoutes.alarms ?? '/admin'}
                className="flex h-10 items-center rounded-[10px] border border-line-strong px-4 text-sm font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
              >
                {alarms.all}
              </Link>
            }
          />
        </main>
      </div>
      <AdminTabs activeId="overview" />
      <CreateUserDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  )
}
