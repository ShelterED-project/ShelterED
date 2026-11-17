import { useCurrentUser } from '@/features/auth/useCurrentUser'
import type { ParentChild } from '@/features/parent/parentApi'
import { childLabel } from '@/features/parent/useParentChildren'
import { childPicker, greeting } from '../content'

type Props = {
  childList: ParentChild[]
  selected: ParentChild | null
  onChange: (childId: string) => void
  title?: string
}

export default function MobileGreeting({ childList, selected, onChange, title }: Props) {
  const user = useCurrentUser()
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{greeting.date}</p>
      <h1 className="pb-[17px] font-heading text-[26px] leading-[32.5px] tracking-[-0.26px] text-parchment">
        {title ?? `${greeting.hello}, ${user?.display_name ?? ''}!`}
      </h1>
      {childList.length > 1 && selected ? (
        <fieldset>
          <legend className="sr-only">{childPicker.label}</legend>
          <div className="flex gap-1 rounded-xl border border-line bg-surface p-1">
            {childList.map((c) => (
              <label
                key={c.child_id}
                className="flex h-10 min-w-0 flex-1 cursor-pointer items-center justify-center truncate rounded-lg px-2 text-sm font-semibold text-muted has-checked:bg-surface-2 has-checked:text-accent has-checked:shadow-[inset_0_0_0_1px_var(--color-line-strong)] has-focus-visible:ring-2 has-focus-visible:ring-accent/40"
              >
                <input
                  type="radio"
                  name="child"
                  value={c.child_id}
                  checked={selected.child_id === c.child_id}
                  onChange={() => onChange(c.child_id)}
                  className="sr-only"
                />
                {c.display_name}
              </label>
            ))}
          </div>
        </fieldset>
      ) : (
        selected && <p className="text-sm text-muted">{childLabel(selected)}</p>
      )}
    </div>
  )
}
