import { childLabel, useParentChildren } from '@/features/parent/useParentChildren'
import { settingsTitle } from '@/pages/settings/content'
import DeviceCard from '@/pages/settings/sections/DeviceCard'
import ProfileCard from '@/pages/settings/sections/ProfileCard'
import SignOutCard from '@/pages/settings/sections/SignOutCard'
import { card, heading } from '@/pages/settings/sections/styles'
import { parentSettings as t } from './content'
import LinkChild from './sections/LinkChild'
import MobileHeader from './sections/MobileHeader'
import MobileTabs from './sections/MobileTabs'
import Sidebar from './sections/Sidebar'
import TopBar from './sections/TopBar'

export default function ParentSettingsPage() {
  const { children, selected, select } = useParentChildren()

  return (
    <div className="flex min-h-screen">
      <Sidebar activeId="settings" />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileHeader />
        <TopBar childList={children} selected={selected} onChange={select} title={settingsTitle} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:gap-6 md:px-10 md:py-8">
          <h1 className="font-heading text-[26px] leading-[32.5px] text-parchment md:hidden">{settingsTitle}</h1>
          <div className="grid gap-5 xl:grid-cols-2 xl:items-start xl:gap-6">
            <div className="flex flex-col gap-5 xl:gap-6">
              <ProfileCard />
              <section className={card}>
                <h2 className={heading}>{t.childrenTitle}</h2>
                {children.length === 0 ? (
                  <p className="text-sm text-muted">{t.noChildren}</p>
                ) : (
                  <ul className="flex flex-col">
                    {children.map((child, i) => (
                      <li
                        key={child.child_id}
                        className={`py-3 text-[15px] font-semibold text-parchment ${i > 0 ? 'border-t border-line-soft' : ''}`}
                      >
                        {childLabel(child)}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <LinkChild onLinked={select} />
            </div>
            <div className="flex flex-col gap-5 xl:gap-6">
              <DeviceCard />
              <SignOutCard />
            </div>
          </div>
        </main>
      </div>
      <MobileTabs activeId="more" />
    </div>
  )
}
