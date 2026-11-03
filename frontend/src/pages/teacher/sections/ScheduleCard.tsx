import { schedule } from '../content'

export default function ScheduleCard() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{schedule.title}</h2>
      <ol>
        {schedule.rows.map((row, i) => (
          <li
            key={row.time}
            className={`flex items-center gap-4 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}
          >
            <span className="w-11 shrink-0 text-sm text-dim md:w-12">{row.time}</span>
            <span
              className={`min-w-0 flex-1 text-[15px] leading-[22.5px] font-medium ${
                row.current ? 'text-parchment' : i < 2 ? 'text-dim' : 'text-parchment'
              }`}
            >
              {row.subject}
            </span>
            {row.current ? (
              <span className="rounded-md bg-accent px-2 py-1 text-xs leading-4 font-semibold text-oil">
                {row.status}
              </span>
            ) : (
              <span className="text-xs leading-4 font-semibold whitespace-nowrap text-dim">{row.status}</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
