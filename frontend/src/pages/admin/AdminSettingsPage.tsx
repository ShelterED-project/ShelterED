import { useState } from 'react'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import DeviceCard from '@/pages/settings/sections/DeviceCard'
import ProfileCard from '@/pages/settings/sections/ProfileCard'
import SignOutCard from '@/pages/settings/sections/SignOutCard'
import { schoolSettings as t } from './content'
import AdminHeader from './sections/AdminHeader'
import AdminSidebar from './sections/AdminSidebar'
import AdminTabs from './sections/AdminTabs'
import CreateUserDialog from './sections/CreateUserDialog'
import MobileGreeting from './sections/MobileGreeting'
import SchoolAlertsCard from './sections/SchoolAlertsCard'

export default function AdminSettingsPage() {
  const [creating, setCreating] = useState(false)
  const user = useCurrentUser()

  return (
    <div className="flex min-h-screen">
      <AdminSidebar activeId="settings" />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader onAddUser={() => setCreating(true)} title={t.title} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting title={t.title} />
          {user?.school_id && <SchoolAlertsCard schoolId={user.school_id} />}
          <div className="grid gap-5 xl:grid-cols-2 xl:items-start xl:gap-6">
            <div className="flex flex-col gap-5 xl:gap-6">
              <ProfileCard />
              <SignOutCard />
            </div>
            <DeviceCard />
          </div>
        </main>
      </div>
      <AdminTabs activeId={null} />
      <CreateUserDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  )
}
