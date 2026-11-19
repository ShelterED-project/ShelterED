import { settingsTitle } from '@/pages/settings/content'
import { studentSettings } from './content'
import PageHeader, { MobileTitle } from './sections/PageHeader'
import {
  DeviceSection,
  MoleNote,
  OfflineSection,
  ProfileSection,
  QuietSection,
  SignOut,
  SyncSection,
} from './sections/SettingsSections'
import StudentSidebar from './sections/StudentSidebar'
import StudentTabs from './sections/StudentTabs'

/** Налаштування учня: лише справжні стани й дії, жодних перемикачів без функції за ними. */
export default function SettingsPage() {
  return (
    <div className="flex min-h-screen">
      <StudentSidebar activeId="settings" />
      <div className="flex min-w-0 flex-1 flex-col">
        <PageHeader title={settingsTitle} subtitle={studentSettings.subtitle} />
        <main className="flex flex-col gap-6 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:px-10 xl:py-8">
          <MobileTitle title={settingsTitle} subtitle={studentSettings.subtitle} />
          <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
            <div className="flex flex-col gap-6">
              <ProfileSection />
              <QuietSection />
              <OfflineSection />
            </div>
            <div className="flex flex-col gap-6">
              <SyncSection />
              <DeviceSection />
              <MoleNote />
              <SignOut />
            </div>
          </div>
        </main>
      </div>
      <StudentTabs activeId={null} />
    </div>
  )
}
