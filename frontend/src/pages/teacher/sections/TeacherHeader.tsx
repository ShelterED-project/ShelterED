import iconChevron from '@/assets/parent/chevron-down.svg'
import iconShield from '@/assets/student/header-shield.svg'
import iconAlarm from '@/assets/teacher/alarm-bell.svg'
import LogoutButton from '@/features/auth/LogoutButton'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import Brand from '@/shared/ui/Brand'
import { useTeacherRollCall } from '@/features/teacher/useTeacherRollCall'
import { greeting, greetingSubtitle, manualAlarm } from '../content'

export default function TeacherHeader() {
  const user = useCurrentUser()
  const { teacherClass, isLoading } = useTeacherRollCall()
  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-3 border-b border-line-soft bg-oil/95 px-5 backdrop-blur-sm md:px-8 xl:h-20 xl:px-10">
      <div className="md:hidden">
        <Brand size="app" />
      </div>
      <div className="hidden min-w-0 md:block">
        <h1 className="truncate font-heading text-2xl leading-[30px] text-parchment xl:text-[28px] xl:leading-[35px]">
          {greeting.hello}, {user?.fullName}
        </h1>
        <p className="truncate text-sm text-dim">{greetingSubtitle(teacherClass?.name)}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2 md:gap-3">
        <div className="relative hidden md:block">
          <select
            aria-label="Клас"
            value={teacherClass?.id ?? ''}
            onChange={() => {}}
            className="h-11 appearance-none rounded-[10px] border border-line bg-surface pr-9 pl-4 text-sm font-semibold text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {/* Поки показуємо перший клас вчителя; вибір між кількома класами — окремий крок. */}
            <option value={teacherClass?.id ?? ''}>
              {teacherClass?.name ?? (isLoading ? greeting.loadingClass : greeting.noClass)}
            </option>
          </select>
          <img
            src={iconChevron}
            alt=""
            width={16}
            height={16}
            className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90"
          />
        </div>
        {/* TODO: запускати ручну тривогу, коли зʼявиться модуль тривог */}
        <button
          type="button"
          aria-label={manualAlarm.full}
          className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-4 text-sm font-semibold text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none md:w-11 md:rounded-xl md:border-line md:px-0 xl:w-auto xl:rounded-[10px] xl:border-line-strong xl:px-4"
        >
          <img src={iconAlarm} alt="" width={18} height={18} className="shrink-0" />
          <span className="md:sr-only xl:not-sr-only">
            <span className="xl:hidden">{manualAlarm.short}</span>
            <span className="hidden xl:inline">{manualAlarm.full}</span>
          </span>
        </button>
        <button
          type="button"
          aria-label="Безпека"
          className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-line focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <img src={iconShield} alt="" width={20} height={20} />
        </button>
        <LogoutButton compact className="size-11 shrink-0 rounded-xl border border-line md:hidden" />
      </div>
    </header>
  )
}
