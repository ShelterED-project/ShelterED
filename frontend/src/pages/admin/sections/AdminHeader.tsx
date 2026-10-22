import iconSettings from '@/assets/student/header-shield.svg'
import iconPlus from '@/assets/admin/plus-dark.svg'
import iconSearch from '@/assets/admin/search.svg'
import Brand from '@/shared/ui/Brand'
import { school } from '../content'

export default function AdminHeader() {
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-line-soft bg-oil/95 px-5 backdrop-blur-sm md:px-8 xl:h-20 xl:px-10">
      <div className="md:hidden">
        <Brand size="app" />
      </div>
      <div className="hidden min-w-0 md:block">
        <h1 className="truncate font-heading text-2xl leading-[30px] text-parchment xl:text-[28px] xl:leading-[35px]">
          {school.name}
        </h1>
        <p className="truncate text-sm text-dim">
          {school.subtitle} · {school.date}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <div className="relative hidden w-[230px] xl:block">
          <img
            src={iconSearch}
            alt=""
            width={18}
            height={18}
            className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2"
          />
          {/* TODO: підключити пошук, коли зʼявляться дані учнів, класів і вчителів */}
          <input
            type="search"
            aria-label="Пошук учня, класу, вчителя"
            placeholder="Пошук учня, класу, вчителя"
            className="h-12 w-full rounded-[10px] border border-line bg-surface pr-3 pl-10 text-sm text-parchment placeholder:text-dim focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          />
        </div>
        {/* TODO: відкривати форму додавання користувача, коли зʼявиться відповідна сторінка */}
        <button
          type="button"
          aria-label="Додати користувача"
          className="flex h-11 items-center justify-center gap-2 rounded-[10px] bg-accent px-4 text-sm font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
        >
          <img src={iconPlus} alt="" width={18} height={18} />
          <span className="hidden md:inline">Додати користувача</span>
        </button>
        <button
          type="button"
          aria-label="Налаштування"
          className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-line focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <img src={iconSettings} alt="" width={20} height={20} />
        </button>
      </div>
    </header>
  )
}
