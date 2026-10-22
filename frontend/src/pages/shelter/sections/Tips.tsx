import { tips } from '../content'

export default function Tips() {
  return (
    <section className="flex flex-col gap-4 rounded-3xl border border-line bg-surface p-5 xl:p-6">
      <h2 className="font-heading text-lg leading-7 tracking-[-0.18px] text-parchment">{tips.title}</h2>
      <ol className="flex flex-col gap-3">
        {tips.items.map((tip, i) => (
          <li key={tip.title} className="flex items-start gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs leading-4 font-bold text-accent">
              {i + 1}
            </span>
            <div className="flex flex-col gap-0.5">
              <p className="text-sm leading-5 font-semibold text-parchment">{tip.title}</p>
              <p className="text-xs leading-4 text-dim">{tip.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
