import { useState } from 'react'
import iconAlarm from '@/assets/teacher/alarm-bell.svg'
import { useTeacherAlarm } from '@/features/teacher/useTeacherAlarm'
import { manualAlarm } from '../content'

const menuButton =
  'h-11 w-full rounded-[10px] px-4 text-left text-sm font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50'

/**
 * Кнопка «Тривога» вчителя. Спершу вибір, щоб не оголосити справжню тривогу випадково:
 * тренувальна, справжня або скасування. Для активної ручної тривоги замість цього «Відбій».
 */
export default function ManualAlarm() {
  const { canStart, manualAlert, busy, error, start, end } = useTeacherAlarm()
  const [open, setOpen] = useState(false)

  const choose = async (isDrill: boolean) => {
    await start(isDrill)
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={manualAlarm.full}
        aria-expanded={open}
        disabled={!canStart || busy}
        onClick={() => (manualAlert ? void end() : setOpen(!open))}
        className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-4 text-sm font-semibold text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50 md:w-11 md:rounded-xl md:border-line md:px-0 xl:w-auto xl:rounded-[10px] xl:border-line-strong xl:px-4"
      >
        <img src={iconAlarm} alt="" width={18} height={18} className="shrink-0" />
        <span className="md:sr-only xl:not-sr-only">
          {manualAlert ? (
            manualAlarm.end
          ) : (
            <>
              <span className="xl:hidden">{manualAlarm.short}</span>
              <span className="hidden xl:inline">{manualAlarm.full}</span>
            </>
          )}
        </span>
      </button>

      {open && !manualAlert && (
        <div
          role="dialog"
          aria-label={manualAlarm.full}
          onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
          className="absolute right-0 z-20 mt-2 flex w-64 flex-col gap-1 rounded-2xl border border-line bg-surface p-2 shadow-lg"
        >
          <p className="px-4 pt-2 pb-1 text-xs text-dim">{manualAlarm.choose}</p>
          <button type="button" disabled={busy} onClick={() => void choose(true)} className={`${menuButton} text-parchment hover:bg-surface-2`}>
            {manualAlarm.drill}
          </button>
          <button type="button" disabled={busy} onClick={() => void choose(false)} className={`${menuButton} bg-accent text-oil`}>
            {manualAlarm.real}
          </button>
          <button type="button" onClick={() => setOpen(false)} className={`${menuButton} text-muted hover:bg-surface-2`}>
            {manualAlarm.cancel}
          </button>
          {error && (
            <p role="alert" className="px-4 pb-2 text-xs font-semibold text-accent">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
