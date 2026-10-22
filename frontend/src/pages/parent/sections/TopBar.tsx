import iconChevron from '@/assets/parent/chevron-down.svg'
import { children, greeting } from '../content'
import type { ChildId } from '../content'
import BellButton from './BellButton'

type Props = { childId: ChildId; onChange: (id: ChildId) => void }

export default function TopBar({ childId, onChange }: Props) {
  const child = children.find((c) => c.id === childId) ?? children[0]
  return (
    <header className="sticky top-0 z-10 hidden h-20 items-center justify-between gap-4 border-b border-line-soft bg-oil/95 px-10 backdrop-blur-sm md:flex">
      <div>
        <h1 className="font-heading text-[28px] leading-[35px] tracking-[-0.28px] text-parchment">{greeting.title}</h1>
        <p className="text-sm text-dim">
          {greeting.date} · {child.name}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <div className="relative">
          <select
            aria-label="Дитина"
            value={childId}
            onChange={(e) => onChange(e.target.value as ChildId)}
            className="h-11 appearance-none rounded-[10px] border border-line bg-surface pr-9 pl-4 text-sm font-semibold text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {children.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <img
            src={iconChevron}
            alt=""
            width={16}
            height={16}
            className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rotate-90"
          />
        </div>
        <BellButton />
      </div>
    </header>
  )
}
