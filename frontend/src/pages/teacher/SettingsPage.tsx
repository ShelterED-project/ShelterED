import { Link } from 'react-router'
import { useClassesQuery } from '@/features/teacher/teacherApi'
import { settingsTitle } from '@/pages/settings/content'
import DeviceCard from '@/pages/settings/sections/DeviceCard'
import ProfileCard from '@/pages/settings/sections/ProfileCard'
import SignOutCard from '@/pages/settings/sections/SignOutCard'
import { card, heading } from '@/pages/settings/sections/styles'
import { navRoutes, sidebarNav, teacherSettings as t } from './content'
import TeacherHeader from './sections/TeacherHeader'
import TeacherSidebar from './sections/TeacherSidebar'
import TeacherTabs from './sections/TeacherTabs'

/** Розділи, яких немає у вкладках телефона: на телефоні до них ведуть звідси. */
const extraSections = sidebarNav.filter((item) => ['schedule', 'map', 'sync'].includes(item.id))

export default function SettingsPage() {
  const classes = useClassesQuery()
  const classNames = (classes.data ?? []).map((c) => c.name).join(', ')

  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="settings" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <h1 className="font-heading text-2xl leading-[30px] text-parchment">{settingsTitle}</h1>

          <section className={`${card} md:hidden`}>
            <h2 className={heading}>{t.sectionsTitle}</h2>
            <ul className="flex flex-col">
              {extraSections.map((item, i) => (
                <li key={item.id} className={i > 0 ? 'border-t border-line-soft' : ''}>
                  <Link
                    to={navRoutes[item.id] ?? '/teacher'}
                    className="flex h-12 items-center justify-between text-[15px] font-semibold text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
                  >
                    {item.label}
                    <span aria-hidden="true" className="text-dim">
                      ›
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <div className="grid gap-5 xl:grid-cols-2 xl:items-start xl:gap-6">
            <div className="flex flex-col gap-5 xl:gap-6">
              <ProfileCard>{classNames && <p className="text-sm text-parchment">{t.classes(classNames)}</p>}</ProfileCard>
              <SignOutCard />
            </div>
            <DeviceCard />
          </div>
        </main>
      </div>
      <TeacherTabs activeId="more" />
    </div>
  )
}
