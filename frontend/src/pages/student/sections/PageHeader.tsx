import { useLocation } from 'react-router'
import { useConnection } from '@/features/sync/useConnection'
import Brand from '@/shared/ui/Brand'
import SettingsLink from '@/shared/ui/SettingsLink'
import { lessonPage as texts, navRoutes } from '../content'

/**
 * Шапка сторінок учня з назвою: на планшеті й десктопі заголовок і підпис, на телефоні бренд
 * (там заголовок у тілі сторінки). Праворуч стан мережі й (на телефоні) налаштування.
 */
export default function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  const { online } = useConnection()
  const { pathname } = useLocation()
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
        <span
          role="status"
          className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs leading-4 font-bold ${online ? 'bg-safe/15 text-safe' : 'bg-line-soft text-accent'}`}
        >
          <span className={`size-1.5 rounded-full ${online ? 'bg-safe' : 'bg-accent'}`} />
          {online ? texts.online : texts.offline}
        </span>
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
