import { steps } from '../content'

export default function HowItWorks() {
  return (
    <section id="how" className="border-t border-line-soft">
      <div className="mx-auto max-w-[1296px] px-5 pt-16 pb-12 md:px-8 lg:pt-[85px] lg:pb-20 xl:px-[72px]">
        <p className="text-xs font-bold tracking-[2px] text-accent uppercase">Як це працює</p>
        <h2 className="mt-4 max-w-[720px] font-heading text-[26px] leading-[1.25] text-parchment md:text-[34px]">
          Від ранку до відбою навчання не обривається
        </h2>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <li key={s.title} className="flex flex-col gap-3 rounded-[20px] border border-line bg-surface p-6">
              <span
                className={`relative flex size-10 items-center justify-center rounded-full font-bold ${
                  i === 1 ? 'border-[3px] border-parchment bg-oil text-parchment' : 'bg-accent text-oil'
                }`}
              >
                {i === 1 && <span className="absolute -inset-[3px] rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />}
                <span className="relative">{i + 1}</span>
              </span>
              <h3 className="font-heading text-lg leading-snug text-parchment">{s.title}</h3>
              <p className="text-[15px] leading-6 text-muted">{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
