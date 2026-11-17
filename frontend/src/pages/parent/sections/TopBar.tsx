import iconChevron from '@/assets/parent/chevron-down.svg'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import type { ParentChild } from '@/features/parent/parentApi'
import { childLabel } from '@/features/parent/useParentChildren'
import { childPicker, greeting } from '../content'
import BellButton from './BellButton'

type Props = {
  childList: ParentChild[]
  selected: ParentChild | null
  onChange: (childId: string) => void
  /** Заголовок сторінки; без нього — привітання */
  title?: string
}

export default function TopBar({ childList, selected, onChange, title }: Props) {
  const user = useCurrentUser()
  return (
    <header className="sticky top-0 z-10 hidden h-20 items-center justify-between gap-4 border-b border-line-soft bg-oil/95 px-10 backdrop-blur-sm md:flex">
      <div className="min-w-0">
        <h1 className="font-heading text-[28px] leading-[35px] tracking-[-0.28px] text-parchment">
          {title ?? `${greeting.hello}, ${user?.display_name ?? ''}!`}
        </h1>
        <p className="truncate text-sm text-dim">
          {greeting.date}
          {selected && ` · ${childLabel(selected)}`}
        </p>
      </div>
      <div className="flex items-center gap-3">
        {childList.length > 1 && selected && (
          <div className="relative">
            <select
              aria-label={childPicker.label}
              value={selected.child_id}
              onChange={(e) => onChange(e.target.value)}
              className="h-11 appearance-none rounded-[10px] border border-line bg-surface pr-9 pl-4 text-sm font-semibold text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            >
              {childList.map((c) => (
                <option key={c.child_id} value={c.child_id}>
                  {c.display_name}
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
        )}
        <BellButton />
      </div>
    </header>
  )
}
