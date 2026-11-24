import { useCallback, useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

interface Drag {
  id: string
  pointerId: number
  order: string[]
  /** Середини інших елементів у координатах сторінки (знімок на початку перетягування) */
  mids: { id: string; mid: number }[]
}

/**
 * Перетягування елементів списку за ручку на Pointer Events: однаково працює мишею, пальцем
 * і стилусом, без бібліотек. Поки тягнемо, список показується в новому порядку; відпустили —
 * onReorder з усіма id. Кнопки ↑/↓ (move) — для клавіатури й тих, кому незручно тягнути.
 *
 * Рух і відпускання слухаємо на window, а не на ручці: коли порядок змінюється, React
 * переставляє DOM-вузол ручки, браузер знімає pointer capture, і pointerup на ній не приходить.
 */
export function useSortable(ids: string[], onReorder: (ids: string[]) => void) {
  const [drag, setDrag] = useState<Drag | null>(null)
  const items = useRef(new Map<string, HTMLElement>())
  const latest = useRef({ ids, onReorder })
  useEffect(() => {
    latest.current = { ids, onReorder }
  })

  const itemRef = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) items.current.set(id, el)
      else items.current.delete(id)
    },
    [],
  )

  const active = drag !== null
  const dragRef = useRef<Drag | null>(null)
  useEffect(() => {
    dragRef.current = drag
  }, [drag])

  useEffect(() => {
    if (!active) return
    const onMove = (e: PointerEvent) => {
      const d = dragRef.current
      if (!d || e.pointerId !== d.pointerId) return
      // Біля краю екрана прокручуємо, щоб можна було перетягнути далеко.
      if (e.clientY < 80) window.scrollBy(0, -12)
      else if (e.clientY > window.innerHeight - 80) window.scrollBy(0, 12)
      const y = e.clientY + window.scrollY
      const target = d.mids.filter((m) => m.mid < y).length
      const rest = d.mids.map((m) => m.id)
      const order = [...rest.slice(0, target), d.id, ...rest.slice(target)]
      if (order.join() !== d.order.join()) setDrag({ ...d, order })
    }
    const onUp = (e: PointerEvent) => {
      const d = dragRef.current
      if (!d || e.pointerId !== d.pointerId) return
      if (d.order.join() !== latest.current.ids.join()) latest.current.onReorder(d.order)
      setDrag(null)
    }
    const onCancel = () => setDrag(null)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onCancel)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onCancel)
    }
  }, [active])

  const handleProps = (id: string) => ({
    onPointerDown: (e: ReactPointerEvent<HTMLElement>) => {
      if (e.button !== 0 || ids.length < 2) return
      e.preventDefault()
      const mids = ids
        .filter((x) => x !== id)
        .map((x) => {
          const r = items.current.get(x)?.getBoundingClientRect()
          return { id: x, mid: r ? r.top + window.scrollY + r.height / 2 : 0 }
        })
      setDrag({ id, pointerId: e.pointerId, order: ids, mids })
    },
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
