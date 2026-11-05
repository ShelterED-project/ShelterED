import iconSound from '@/assets/shelter/sound-off.svg'
import { alert } from '../content'

export default function AlertStrip() {
  return (
    <div role="alert" className="border-b border-accent/40 bg-accent-soft">
      <div className="mx-auto flex h-11 max-w-[1296px] items-center gap-3 px-5 md:px-8 xl:px-10">
        <span className="size-2.5 shrink-0 rounded-full bg-accent" />
        <p className="text-sm leading-5 font-bold whitespace-nowrap text-accent">{alert.title}</p>
        <p className="min-w-0 truncate text-sm leading-5 text-muted">
          <span className="hidden md:inline">{alert.region} · </span>
          {alert.since}
        </p>
        <p className="ml-auto hidden items-center gap-1.5 text-xs text-dim md:flex">
          <img src={iconSound} alt="" width={16} height={16} />
          {alert.sound}
        </p>
      </div>
    </div>
  )
}
