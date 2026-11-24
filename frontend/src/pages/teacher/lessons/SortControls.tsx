import type { useSortable } from './useSortable'
import { editor } from './content'
import { iconButton } from './styles'

type Sortable = ReturnType<typeof useSortable>

/** Ручка для перетягування й кнопки ↑/↓ (для клавіатури). */
export default function SortControls({
  sortable,
  id,
  index,
  count,
  disabled,
}: {
  sortable: Sortable
  id: string
  index: number
  count: number
  disabled?: boolean
}) {
  if (disabled || count < 2) return null
  return (
    <div className="flex shrink-0 items-center">
      <button
        type="button"
        aria-label={editor.dragHandle}
        title={editor.dragHandle}
        {...sortable.handleProps(id)}
        className={`${iconButton} cursor-grab text-lg active:cursor-grabbing`}
      >
        ⠿
      </button>
      <button
        type="button"
        aria-label={editor.moveUp}
        title={editor.moveUp}
        disabled={index === 0}
        onClick={() => sortable.move(id, -1)}
        className={`${iconButton} hidden md:inline-flex`}
      >
        ↑
      </button>
      <button
        type="button"
        aria-label={editor.moveDown}
        title={editor.moveDown}
        disabled={index === count - 1}
        onClick={() => sortable.move(id, 1)}
        className={`${iconButton} hidden md:inline-flex`}
      >
        ↓
      </button>
    </div>
  )
}
