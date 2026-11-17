import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { settingsTitle } from '@/pages/settings/content'
import DeviceCard from '@/pages/settings/sections/DeviceCard'
import ProfileCard from '@/pages/settings/sections/ProfileCard'
import SignOutCard from '@/pages/settings/sections/SignOutCard'
import { studentSettings } from './content'
import StudentHeader from './sections/StudentHeader'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'

export default function SettingsPage() {
  const pending = useOutboxCount()
  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="settings" />
      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader pending={pending} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <h1 className="font-heading text-2xl leading-[30px] text-parchment">{settingsTitle}</h1>
          <div className="grid gap-5 xl:grid-cols-2 xl:items-start xl:gap-6">
            <div className="flex flex-col gap-5 xl:gap-6">
              <ProfileCard note={studentSettings.pinNote} />
              <SignOutCard />
            </div>
            <DeviceCard showPacks />
          </div>
        </main>
      </div>
      <StudentTabs activeId={null} />
    </div>
  )
}
