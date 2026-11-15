import { Link } from 'react-router'
import { useTeacherSchedule } from '@/features/teacher/useTeacherSchedule'
import { navRoutes, schedule } from '../content'
import ScheduleList from './ScheduleList'

export default function ScheduleCard() {
  const { rows, isLoading, isOffline } = useTeacherSchedule()

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{schedule.title}</h2>
        <Link
          to={navRoutes.schedule ?? '/teacher'}
          className="rounded text-sm font-semibold whitespace-nowrap text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {schedule.week}
        </Link>
      </div>
      {rows && rows.length > 0 ? (
        <ScheduleList rows={rows} />
      ) : (
        <p role="status" className="text-sm text-muted">
          {isLoading ? schedule.loading : isOffline && !rows ? schedule.offline : schedule.empty}
        </p>
      )}
    </section>
  )
}
