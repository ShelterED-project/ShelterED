import type { ScheduleRow } from '@/features/teacher/useTeacherSchedule'
import { schedule } from '../content'

/** Уроки одного дня: час, предмет, призначений урок і статус «минув / зараз / далі». */
export default function ScheduleList({ rows }: { rows: ScheduleRow[] }) {
  return (
    <ol>
      {rows.map((row, i) => {
        const done = row.status === 'done'
        return (
          <li
            key={row.key}
            aria-current={row.status === 'now' ? 'time' : undefined}
            className={`flex items-center gap-4 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}
          >
            <span className="w-11 shrink-0 text-sm text-dim md:w-12">{row.startsAt}</span>
            <span className="min-w-0 flex-1">
              <span
                className={`block truncate text-[15px] leading-[22.5px] font-medium ${done ? 'text-dim' : 'text-parchment'}`}
              >
                {row.subject}
              </span>
              {(row.lessonTitle || !row.hasLesson) && (
                <span className={`block truncate text-xs leading-4 ${row.hasLesson ? 'text-dim' : 'text-accent'}`}>
                  {row.lessonTitle ?? schedule.notAssigned}
                </span>
              )}
            </span>
            {row.status === 'now' ? (
              <span className="rounded-md bg-accent px-2 py-1 text-xs leading-4 font-semibold text-oil">
                {schedule.status.now}
              </span>
            ) : (
              <span className="text-xs leading-4 font-semibold whitespace-nowrap text-dim">{schedule.status[row.status]}</span>
            )}
          </li>
        )
      })}
    </ol>
  )
}
