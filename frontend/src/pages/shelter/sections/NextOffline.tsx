import { next } from '../content'

export default function NextOffline() {
  return (
    <section className="flex flex-col gap-4 rounded-3xl border border-line bg-surface p-5 xl:p-7">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment xl:text-[22px] xl:tracking-[-0.22px]">
          {next.title}
        </h2>
        <p className="text-right text-xs leading-4 text-dim">{next.hint}</p>
      </div>
      {/* TODO: відкривати матеріал за натисканням, коли зʼявиться сторінка уроку */}
      <ul className="grid gap-3 md:grid-cols-3">
        {next.items.map((item) => (
          <li key={item.name} className="flex flex-col gap-1 rounded-2xl border border-line bg-surface-2/50 p-4">
            <span className="text-xs leading-4 text-dim">{item.subject}</span>
            <span className="text-[15px] leading-[22.5px] font-semibold text-parchment">{item.name}</span>
            <span className="pt-1 text-xs leading-4 text-dim">{item.meta}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
