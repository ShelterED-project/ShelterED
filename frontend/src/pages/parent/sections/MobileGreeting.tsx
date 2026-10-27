import { children, greeting } from '../content'
import type { ChildId } from '../content'

type Props = { childId: ChildId; onChange: (id: ChildId) => void }

export default function MobileGreeting({ childId, onChange }: Props) {
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{greeting.date}</p>
      <h1 className="pb-[17px] font-heading text-[26px] leading-[32.5px] tracking-[-0.26px] text-parchment">
        {greeting.title}
      </h1>
      <fieldset>
        <legend className="sr-only">Дитина</legend>
        <div className="flex gap-1 rounded-xl border border-line bg-surface p-1">
          {children.map((c) => (
            <label
              key={c.id}
              className="flex h-10 flex-1 cursor-pointer items-center justify-center rounded-lg text-sm font-semibold text-muted has-checked:bg-surface-2 has-checked:text-accent has-checked:shadow-[inset_0_0_0_1px_var(--color-line-strong)] has-focus-visible:ring-2 has-focus-visible:ring-accent/40"
            >
              <input
                type="radio"
                name="child"
                value={c.id}
                checked={childId === c.id}
                onChange={() => onChange(c.id)}
                className="sr-only"
              />
              {c.label}
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  )
}
