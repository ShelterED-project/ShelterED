import { save } from './content'
import type { FieldSave } from './useAutosave'

/** Помилка автозбереження конкретного поля (успіх показує загальний індикатор у шапці). */
export default function FieldStatus({ status, error }: { status: FieldSave; error: string | null }) {
  if (status === 'retry') return <p className="text-xs text-dim">{save.fieldRetry}</p>
  if (status === 'error' && error)
    return (
      <p role="alert" className="text-sm font-semibold text-accent">
        {error}
      </p>
    )
  return null
}
