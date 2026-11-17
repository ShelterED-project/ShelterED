import { useLiveQuery } from 'dexie-react-hooks'
import { useAppSelector } from '@/app/hooks'
import { db } from '@/shared/db/db'
import { readMeta, useCached } from '@/shared/db/useCached'
import { useParentChildrenQuery } from './parentApi'
import type { ParentChild } from './parentApi'

const childrenKey = (parentId: string) => `parent_children:${parentId}`
const selectedKey = (parentId: string) => `parent_selected_child:${parentId}`

export function childName(child: Pick<ParentChild, 'display_name' | 'last_name'>): string {
  return [child.display_name, child.last_name].filter(Boolean).join(' ')
}

/** «Марія Бондаренко, 5-А» */
export function childLabel(child: ParentChild): string {
  return child.class_name ? `${childName(child)}, ${child.class_name}` : childName(child)
}

/**
 * Діти батьків і вибрана дитина. Список кешується в IndexedDB, тож кабінет відкривається
 * без мережі; вибір дитини спільний для всіх сторінок кабінету й переживає перезапуск.
 */
export function useParentChildren() {
  const parentId = useAppSelector((s) => s.auth.session?.user.id)
  const query = useParentChildrenQuery(undefined, { skip: !parentId, refetchOnMountOrArgChange: true })
  const children = useCached<ParentChild[]>(parentId ? childrenKey(parentId) : null, query.data)
  const selectedId = useLiveQuery(
    async () => (parentId ? readMeta<string>(selectedKey(parentId)) : null),
    [parentId],
  )

  const list = children ?? []
  const selected = list.find((child) => child.child_id === selectedId) ?? list[0] ?? null

  const select = (childId: string) => {
    if (parentId) void db.meta.put({ key: selectedKey(parentId), value: childId }).catch(() => undefined)
  }

  return {
    children: list,
    selected,
    select,
    /** Ще не знаємо, чи є діти: ні відповіді сервера, ні кешу */
    isLoading: children === null && query.isLoading,
    isOffline: query.isError,
  }
}
