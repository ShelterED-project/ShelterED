import AdminHeader from './sections/AdminHeader'
import AdminSidebar from './sections/AdminSidebar'
import AdminTabs from './sections/AdminTabs'
import AlarmLog from './sections/AlarmLog'
import AlertBanner from './sections/AlertBanner'
import ClassesCard from './sections/ClassesCard'
import Kpis from './sections/Kpis'
import MobileGreeting from './sections/MobileGreeting'
import UsersCard from './sections/UsersCard'

export default function AdminPage() {
  return (
    <div className="flex min-h-screen">
      <AdminSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting />
          <AlertBanner />
          <Kpis />
          <div className="flex flex-col gap-5 xl:flex-row xl:gap-6">
            <ClassesCard className="xl:min-w-0 xl:flex-1" />
            <UsersCard className="xl:w-[400px] xl:shrink-0" />
          </div>
          <AlarmLog />
        </main>
      </div>
      <AdminTabs />
    </div>
  )
}
