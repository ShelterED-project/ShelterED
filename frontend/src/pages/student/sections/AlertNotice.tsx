import { Link } from 'react-router'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import { alertNotice } from '../content'

/** Банер на головній учня: тривога триває, а учень повернувся зі режиму укриття. */
export default function AlertNotice() {
  const { alert } = useActiveAlert()
  if (!alert) return null

  return (
    <section
      role="alert"
      className="flex flex-col gap-3 rounded-[22px] border border-accent/40 bg-accent-soft p-5 md:flex-row md:items-center"
    >
      <p className="flex-1 text-[17px] leading-[25.5px] font-semibold text-accent">
        {alert.is_drill ? alertNotice.drillTitle : alertNotice.title}
      </p>
      <Link
        to="/shelter"
        className="flex h-12 items-center justify-center rounded-[10px] bg-accent px-6 text-[15px] font-semibold whitespace-nowrap text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
      >
        {alertNotice.open}
      </Link>
    </section>
  )
}
