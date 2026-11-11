import iconLantern from '@/assets/admin/alert-lantern.svg'
import { useTeacherAlarm } from '@/features/teacher/useTeacherAlarm'
import { useTeacherRollCall } from '@/features/teacher/useTeacherRollCall'
import Spinner from '@/shared/ui/Spinner'
import { alertBanner } from '../content'

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}

const primaryButton =
  'h-12 shrink-0 rounded-[10px] bg-accent px-6 text-[15px] font-semibold whitespace-nowrap text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-50'
const secondaryButton =
  'h-12 shrink-0 rounded-[10px] border border-line-strong px-5 text-[15px] font-semibold whitespace-nowrap text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50'

export default function AlertBanner() {
  const { session, teacherClass, isLoading, isOffline, busy, actionError, start, close } = useTeacherRollCall()
  const alarm = useTeacherAlarm()

  const title = session
    ? session.is_drill
      ? alertBanner.drillTitle
      : alertBanner.activeTitle
    : isLoading
      ? alertBanner.loading
      : alertBanner.idleTitle
  const answered = session ? session.summary.safe + session.summary.in_shelter : 0
  const text = session
    ? `Відмітились ${answered} з ${session.students.length} · відкрита о ${timeLabel(session.opened_at)}`
    : alertBanner.idleText

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-accent/40 bg-surface-2 p-5 md:flex-row md:items-center">
      <div className="relative flex size-12 shrink-0 items-center justify-center rounded-full bg-accent-soft">
        <span className="absolute inset-0 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />
        <img src={iconLantern} alt="" width={24} height={24} className="relative" />
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="text-[17px] leading-[25.5px] font-semibold text-parchment">{title}</h2>
        <p role="status" className="text-sm leading-5 text-muted">{text}</p>
        {isOffline && <p className="text-sm leading-5 text-dim">{alertBanner.offline}</p>}
        {(actionError ?? alarm.error) && (
          <p role="alert" className="text-sm leading-5 font-semibold text-accent">
            {actionError ?? alarm.error}
          </p>
        )}
      </div>
      {session ? (
        <div className="flex flex-col gap-2 md:flex-row">
          {alarm.manualAlert && (
            <button
              type="button"
              onClick={() => void alarm.end()}
              disabled={alarm.busy}
              aria-busy={alarm.busy}
              className={`${primaryButton} inline-flex items-center justify-center gap-2`}
            >
              {alarm.pending === 'end' && <Spinner />}
              {alarm.pending === 'end' ? alertBanner.endingAlarm : alertBanner.endAlarm}
            </button>
          )}
          <button
            type="button"
            onClick={() => void close()}
            disabled={busy}
            className={alarm.manualAlert ? secondaryButton : primaryButton}
          >
            {alertBanner.close}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2 md:flex-row">
          <button
            type="button"
            onClick={() => void start(false)}
            disabled={busy || !teacherClass}
            className={primaryButton}
          >
            {alertBanner.start}
          </button>
          <button
            type="button"
            onClick={() => void start(true)}
            disabled={busy || !teacherClass}
            className={secondaryButton}
          >
            {alertBanner.startDrill}
          </button>
        </div>
      )}
    </section>
  )
}
