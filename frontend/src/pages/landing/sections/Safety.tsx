import { safety } from '../content'

export default function Safety() {
  return (
    <section id="safety" className="border-y border-line-soft bg-surface/40">
      <ul className="mx-auto grid max-w-[1296px] gap-8 px-5 py-12 sm:grid-cols-2 md:px-8 lg:grid-cols-4 lg:py-16 xl:px-[72px]">
        {safety.map((f) => (
          <li key={f.title} className="flex items-start gap-4">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-surface-2">
              <img src={f.icon} alt="" width={20} height={20} />
            </span>
            <div className="flex flex-col gap-[3px]">
              <h3 className="text-base font-bold text-parchment">{f.title}</h3>
              <p className="text-sm leading-[22.75px] text-muted">{f.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
