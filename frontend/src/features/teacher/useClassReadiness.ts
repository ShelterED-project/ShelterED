import { skipToken } from '@reduxjs/toolkit/query/react'
import { usePackManifestQuery } from '@/features/packs/packsApi'
import type { PackManifestItem } from '@/shared/db/packTypes'
import { useClassesQuery, useClassScheduleQuery } from './teacherApi'

/** Стільки днів наперед сервер збирає пакети «Рюкзака». */
const DAYS = 7

export type DayReadiness =
  /** Уроки призначено й пакет зібрано: учні отримають день офлайн */
  | 'ready'
  /** Уроки призначено, а пакета немає (урок не опубліковано або пакет ще збирається) */
  | 'missing'
  /** Слоти є, але жоден урок не призначено */
  | 'unassigned'
  /** Уроків за розкладом немає (вихідний) */
  | 'free'

export interface ReadinessDay {
  date: string
  /** Призначених уроків у розкладі */
  lessons: number
  /** Слотів у розкладі */
  slots: number
  pack: PackManifestItem | null
  state: DayReadiness
}

/**
 * Готовність першого класу вчителя до укриття: чи зібрані пакети уроків на 7 днів наперед.
 * Розклад показує, що призначено, маніфест — що учні справді отримають на пристрої.
 * Без опитування: дані беруться при відкритті сторінки й кнопкою «Оновити».
 */
export function useClassReadiness() {
  const classes = useClassesQuery()
  const teacherClass = classes.data?.[0]
  const classId = teacherClass?.id
  const schedule = useClassScheduleQuery(classId ? { classId, days: DAYS } : skipToken, {
    refetchOnMountOrArgChange: true,
  })
  const manifest = usePackManifestQuery(classId ?? skipToken, { refetchOnMountOrArgChange: true })

  const packs = new Map((manifest.data?.packs ?? []).map((p) => [p.pack_date, p]))
  const days: ReadinessDay[] | null = schedule.data
    ? schedule.data.days.map((day) => {
        const lessons = day.items.filter((item) => item.lesson_id).length
        const pack = packs.get(day.date) ?? null
        const state: DayReadiness =
          day.items.length === 0 ? 'free' : lessons === 0 ? 'unassigned' : pack ? 'ready' : 'missing'
        return { date: day.date, lessons, slots: day.items.length, pack, state }
      })
    : null

  return {
    teacherClass,
    days,
    isLoading: classes.isLoading || schedule.isLoading || manifest.isLoading,
    /** Сервер не відповів на останній запит */
    isOffline: classes.isError || schedule.isError || manifest.isError,
    /** Коли сервер востаннє успішно віддав маніфест (мс) */
    updatedAt: manifest.fulfilledTimeStamp ?? null,
    isFetching: schedule.isFetching || manifest.isFetching,
    refresh: () => {
      if (!classId) return
      void schedule.refetch()
      void manifest.refetch()
    },
  }
}
