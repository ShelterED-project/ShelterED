import iconChevron from '@/assets/student/chevron-right.svg'
import iconCalm from '@/assets/student/calm.svg'
import { calm } from '../content'

export default function CalmCard() {
  return (
    // TODO: відкривати вправу з диханням, коли зʼявиться відповідна сторінка
    <button
      type="button"
      className="flex w-full items-center gap-4 rounded-[22px] border border-line bg-surface p-5 text-left hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
    >
      <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-surface-2">
        <img src={iconCalm} alt="" width={20} height={20} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] leading-[22.5px] font-semibold text-parchment">{calm.title}</span>
        <span className="block text-xs text-dim">{calm.text}</span>
      </span>
      <img src={iconChevron} alt="" width={20} height={20} className="shrink-0" />
    </button>
  )
}
