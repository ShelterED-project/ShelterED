import { useLocation } from 'react-router'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import Brand from '@/shared/ui/Brand'
import SettingsLink from '@/shared/ui/SettingsLink'
import { navRoutes, studentRole } from '../content'

/**
 * Шапка сторінок учня з назвою: на планшеті й десктопі заголовок і підпис, на телефоні бренд
 * (там заголовок у тілі сторінки) і шестерня налаштувань; на планшеті праворуч ім'я учня. Стан мережі в шапці не показуємо:
 * він є в налаштуваннях і на сторінці уроку (черга відправки).
 */
export default function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  const { pathname } = useLocation()
  const user = useCurrentUser()
  const settings = navRoutes.settings ?? '/student/settings'

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-line-soft bg-oil/95 px-5 backdrop-blur-sm md:px-8 xl:h-20 xl:px-10">
      <div className="md:hidden">
        <Brand size="app" />
      </div>
      <div className="hidden min-w-0 md:block">
        <h1 className="truncate font-heading text-2xl leading-[30px] tracking-[-0.24px] text-parchment xl:text-[28px] xl:leading-[35px] xl:tracking-[-0.28px]">
          {title}
        </h1>
        {subtitle && <p className="truncate text-sm leading-5 text-dim">{subtitle}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2 md:gap-3">
        {/* Планшет: меню вузьке й без імені, тож хто увійшов — тут. На десктопі ім'я є в меню. */}
        {user && (
          <div className="hidden items-center gap-3 md:flex xl:hidden">
            <div className="text-right">
              <p className="text-sm leading-5 font-semibold text-parchment">{user.fullName}</p>
              <p className="text-xs leading-4 text-dim">{studentRole}</p>
            </div>
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-sm font-bold text-parchment">
              {user.initials}
            </span>
          </div>
        )}
        {/* На телефоні бічного меню немає: налаштування (і вихід) — через шестерню. */}
        {pathname !== settings && <SettingsLink to={settings} className="md:hidden" />}
      </div>
    </header>
  )
}

/** Заголовок сторінки в тілі на телефоні: у шапці там бренд. */
export function MobileTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="md:hidden">
      {subtitle && <p className="text-sm leading-5 text-dim">{subtitle}</p>}
      <h1 className="font-heading text-[26px] leading-8 tracking-[-0.26px] text-parchment">{title}</h1>
    </div>
  )
}
