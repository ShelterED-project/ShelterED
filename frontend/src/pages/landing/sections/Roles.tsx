import { Link } from 'react-router'
import arrowIcon from '@/assets/landing/icon-arrow.svg'
import { roles } from '../content'

export default function Roles() {
  return (
    <section id="roles" className="mx-auto max-w-[1296px] px-5 pb-16 md:px-8 lg:pb-20 xl:px-[72px]">
      <h2 className="font-heading text-[26px] leading-[1.25] text-parchment md:text-[34px]">
        Один застосунок — кожному своє
      </h2>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {roles.map((r) => (
          <article key={r.title} className="flex flex-col rounded-[20px] border border-line bg-surface-2 p-6">
            <span className="flex size-12 items-center justify-center rounded-xl bg-accent-soft">
              <img src={r.icon} alt="" width={24} height={24} />
            </span>
            <h3 className="mt-5 font-heading text-xl text-parchment">{r.title}</h3>
            <p className="mt-3 flex-1 text-[15px] leading-6 text-muted">{r.text}</p>
            <Link to={r.to} className="mt-6 flex items-center gap-2 rounded text-base font-semibold text-muted hover:text-parchment">
              {r.cta}
              <img src={arrowIcon} alt="" width={16} height={16} />
            </Link>
          </article>
        ))}
      </div>
    </section>
  )
}
