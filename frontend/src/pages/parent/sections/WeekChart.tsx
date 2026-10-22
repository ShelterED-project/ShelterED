import { week } from '../content'

export default function WeekChart({ className = '' }: { className?: string }) {
  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
          {week.title}
        </h2>
        <p className="text-xs text-dim">{week.range}</p>
      </div>

      <div className="flex items-end gap-3 px-1 md:gap-6">
        {week.days.map((d) => (
          <div key={d.day} className="flex min-w-0 flex-1 flex-col items-center gap-2">
            <div
              role="img"
              aria-label={`${d.day}: ${week.legend.regular} ${d.regular} хв, ${week.legend.shelter} ${d.shelter} хв`}
              className="flex h-[150px] w-11 max-w-full flex-col justify-end gap-1"
            >
              {d.shelter > 0 ? (
                <>
                  <div className="w-full rounded-t-md bg-accent" style={{ height: d.shelter }} />
                  <div className="w-full rounded-b-md bg-line-strong" style={{ height: d.regular }} />
                </>
              ) : (
                <div className="w-full rounded-md bg-line-strong" style={{ height: d.regular }} />
              )}
            </div>
            <span className="text-xs text-dim">{d.day}</span>
          </div>
        ))}
      </div>

      <ul className="flex flex-wrap gap-5 pt-1 text-xs text-muted">
        <li className="flex items-center gap-2">
          <span className="size-3 rounded-[2px] bg-line-strong" />
          {week.legend.regular}
        </li>
        <li className="flex items-center gap-2">
          <span className="size-3 rounded-[2px] bg-accent" />
          {week.legend.shelter}
        </li>
      </ul>
    </section>
  )
}
