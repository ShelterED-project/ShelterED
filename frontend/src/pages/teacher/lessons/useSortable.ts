import { useCallback, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

interface Drag {
  id: string
  order: string[]
  /** Середини інших елементів у координатах сторінки (знімок на початку перетягування) */
  mids: { id: string; mid: number }[]
}

/**
 * Перетягування елементів списку за ручку на Pointer Events: однаково працює мишею, пальцем
 * і стилусом, без бібліотек. Поки тягнемо, список показується в новому порядку; відпустили —
 * onReorder з усіма id. Кнопки ↑/↓ (move) — для клавіатури й тих, кому незручно тягнути.
 */
export function useSortable(ids: string[], onReorder: (ids: string[]) => void) {
  const [drag, setDrag] = useState<Drag | null>(null)
  const items = useRef(new Map<string, HTMLElement>())

  const itemRef = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) items.current.set(id, el)
      else items.current.delete(id)
    },
    [],
  )

  const handleProps = (id: string) => ({
    onPointerDown: (e: ReactPointerEvent<HTMLElement>) => {
      if (e.button !== 0 || ids.length < 2) return
      e.preventDefault()
      e.currentTarget.setPointerCapture(e.pointerId)
      const mids = ids
        .filter((x) => x !== id)
        .map((x) => {
          const r = items.current.get(x)?.getBoundingClientRect()
          return { id: x, mid: r ? r.top + window.scrollY + r.height / 2 : 0 }
        })
      setDrag({ id, order: ids, mids })
    },
    onPointerMove: (e: ReactPointerEvent<HTMLElement>) => {
      if (!drag || drag.id !== id) return
      // Біля краю екрана прокручуємо, щоб можна було перетягнути далеко.
      if (e.clientY < 80) window.scrollBy(0, -12)
      else if (e.clientY > window.innerHeight - 80) window.scrollBy(0, 12)
      const y = e.clientY + window.scrollY
      const target = drag.mids.filter((m) => m.mid < y).length
      const rest = drag.mids.map((m) => m.id)
      const order = [...rest.slice(0, target), id, ...rest.slice(target)]
      if (order.join() !== drag.order.join()) setDrag({ ...drag, order })
    },
    onPointerUp: () => {
      if (!drag) return
      if (drag.order.join() !== ids.join()) onReorder(drag.order)
      setDrag(null)
    },
    onPointerCancel: () => setDrag(null),
    style: { touchAction: 'none' as const },
  })

  const move = (id: string, delta: -1 | 1) => {
    const i = ids.indexOf(id)
    const j = i + delta
    if (i < 0 || j < 0 || j >= ids.length) return
    const next = [...ids]
    next.splice(i, 1)
    next.splice(j, 0, id)
    onReorder(next)
  }

  return { order: drag?.order ?? ids, dragging: drag?.id ?? null, handleProps, itemRef, move }
}
