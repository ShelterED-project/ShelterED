import iconPlus from '@/assets/admin/plus-dark.svg'
import iconSearch from '@/assets/admin/search.svg'
import LogoutButton from '@/features/auth/LogoutButton'
import Brand from '@/shared/ui/Brand'
import { school } from '../content'

type Props = {
  onAddUser: () => void
  /** Заголовок сторінки; без нього — школа */
  title?: string
  /** Пошук показується лише там, де є що шукати */
  search?: { value: string; onChange: (value: string) => void; placeholder: string }
}

export default function AdminHeader({ onAddUser, title = school.name, search }: Props) {
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-line-soft bg-oil/95 px-5 backdrop-blur-sm md:px-8 xl:h-20 xl:px-10">
      <div className="md:hidden">
        <Brand size="app" />
      </div>
      <div className="hidden min-w-0 md:block">
        <h1 className="truncate font-heading text-2xl leading-[30px] text-parchment xl:text-[28px] xl:leading-[35px]">
          {title}
        </h1>
        <p className="truncate text-sm text-dim">
          {school.subtitle} · {school.date}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {search && (
          <div className="relative hidden w-[230px] xl:block">
            <img
              src={iconSearch}
              alt=""
              width={18}
              height={18}
              className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2"
            />
            <input
              type="search"
              aria-label={search.placeholder}
              placeholder={search.placeholder}
              value={search.value}
              onChange={(e) => search.onChange(e.target.value)}
              className="h-12 w-full rounded-[10px] border border-line bg-surface pr-3 pl-10 text-sm text-parchment placeholder:text-dim focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            />
          </div>
        )}
        <button
          type="button"
          onClick={onAddUser}
          aria-label="Додати користувача"
          className="flex h-11 items-center justify-center gap-2 rounded-[10px] bg-accent px-4 text-sm font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
        >
          <img src={iconPlus} alt="" width={18} height={18} />
          <span className="hidden md:inline">Додати користувача</span>
        </button>
        <LogoutButton compact className="size-11 shrink-0 rounded-xl border border-line md:hidden" />
      </div>
    </header>
  )
}
