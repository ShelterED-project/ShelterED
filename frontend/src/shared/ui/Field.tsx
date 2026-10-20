import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { useId } from 'react'

type ShellProps = {
  label: string
  icon: string
  hint?: string
  error?: string
  trailing?: ReactNode
  children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode
}

const controlClass =
  'h-12 w-full rounded-[10px] border bg-surface pl-11 text-base text-parchment outline-none placeholder:text-dim focus:border-accent focus-visible:ring-2 focus-visible:ring-accent/40'

function FieldShell({ label, icon, hint, error, trailing, children }: ShellProps) {
  const id = useId()
  const noteId = `${id}-note`
  const note = error ?? hint
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-semibold text-parchment">
        {label}
      </label>
      <div className="relative">
        {children({ id, describedBy: note ? noteId : undefined, invalid: Boolean(error) })}
        <img src={icon} alt="" width={18} height={18} className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2" />
        {trailing}
      </div>
      {note && (
        <p id={noteId} className={`text-xs ${error ? 'text-danger' : 'text-dim'}`}>
          {note}
        </p>
      )}
    </div>
  )
}

type CommonProps = Pick<ShellProps, 'label' | 'icon' | 'hint' | 'error' | 'trailing'>

export function TextField({
  label,
  icon,
  hint,
  error,
  trailing,
  className = '',
  ...input
}: CommonProps & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <FieldShell label={label} icon={icon} hint={hint} error={error} trailing={trailing}>
      {({ id, describedBy, invalid }) => (
        <input
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${controlClass} ${trailing ? 'pr-12' : 'pr-4'} ${invalid ? 'border-danger' : 'border-line'} ${className}`}
          {...input}
        />
      )}
    </FieldShell>
  )
}

export function SelectField({
  label,
  icon,
  hint,
  error,
  children,
  ...select
}: CommonProps & SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <FieldShell label={label} icon={icon} hint={hint} error={error}>
      {({ id, describedBy, invalid }) => (
        <select
          id={id}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={`${controlClass} pr-4 ${invalid ? 'border-danger' : 'border-line'}`}
          {...select}
        >
          {children}
        </select>
      )}
    </FieldShell>
  )
}
