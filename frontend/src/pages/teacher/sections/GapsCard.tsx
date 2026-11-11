import { Link } from 'react-router'
import { useClassGaps } from '@/features/teacher/useClassResults'
import { gaps as text, navRoutes } from '../content'

export default function GapsCard() {
  const { gaps, isLoading, isOffline } = useClassGaps()
  // Сервер віддає теми від найнижчої середньої оцінки; на огляді лише перші, з оцінками.
  const scored = gaps?.topics.filter((topic) => topic.tests_scored > 0) ?? []
  const rows = scored.slice(0, text.limit)
  const hasGaps = scored.some((topic) => topic.is_gap)

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{text.title}</h2>
        <Link
          to={navRoutes.map ?? '/teacher'}
          className="rounded text-sm font-semibold whitespace-nowrap text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {text.map}
        </Link>
      </div>
      {rows.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {rows.map((topic) => (
            <li key={topic.lesson_id} className="flex items-center gap-3">
              <span
                className={`flex size-9 shrink-0 items-center justify-center rounded-full border-2 border-dashed text-xs leading-4 font-semibold text-parchment ${
                  topic.is_gap ? 'border-accent' : 'border-muted'
                }`}
              >
                {topic.tests_scored - topic.tests_passed}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] leading-[22.5px] text-parchment">{topic.title}</span>
                <span className="block truncate text-xs leading-4 text-dim">{topic.subject_name}</span>
              </span>
              <span
                className="h-2 w-24 shrink-0 rounded-full bg-line-soft"
                role="img"
                aria-label={`Середня оцінка ${Math.round(topic.avg_score ?? 0)}%`}
              >
                <span
                  className={`block h-2 rounded-full ${topic.is_gap ? 'bg-accent' : 'bg-safe'}`}
                  style={{ width: `${Math.min(100, Math.max(0, topic.avg_score ?? 0))}%` }}
                />
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p role="status" className="text-sm text-muted">
          {isLoading ? text.loading : text.empty}
        </p>
      )}
      {rows.length > 0 && !hasGaps && <p className="text-sm text-muted">{text.noGaps}</p>}
      {isOffline && <p className="text-sm text-dim">{text.offline}</p>}
      <p className="text-xs leading-4 text-dim">{text.note}</p>
    </section>
  )
}
