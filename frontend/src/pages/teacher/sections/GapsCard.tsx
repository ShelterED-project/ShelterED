import { gaps } from '../content'

export default function GapsCard() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{gaps.title}</h2>
        {/* TODO: відкривати мапу класу, коли зʼявиться відповідна сторінка */}
        <button
          type="button"
          className="rounded text-sm font-semibold whitespace-nowrap text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {gaps.map}
        </button>
      </div>
      <ul className="flex flex-col gap-3">
        {gaps.rows.map((row) => (
          <li key={row.topic} className="flex items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full border-2 border-dashed border-muted text-xs leading-4 font-semibold text-parchment">
              {row.count}
            </span>
            <span className="min-w-0 flex-1 text-[15px] leading-[22.5px] text-parchment">{row.topic}</span>
            <span className="h-2 w-24 shrink-0 rounded-full bg-line-soft">
              <span className="block h-2 rounded-full bg-accent" style={{ width: `${row.share}%` }} />
            </span>
          </li>
        ))}
      </ul>
      <p className="text-xs leading-4 text-dim">{gaps.note}</p>
    </section>
  )
}
