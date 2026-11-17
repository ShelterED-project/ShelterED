import { useEffect } from 'react'
import { skipToken } from '@reduxjs/toolkit/query/react'
import { useLiveQuery } from 'dexie-react-hooks'
import { useAppSelector } from '@/app/hooks'
import { db } from '@/shared/db/db'
import { useStudentProgressQuery } from './studentApi'
import type { StudentProgress } from './studentApi'

const cacheKey = (studentId: string) => `student_progress:${studentId}`

/**
 * Прогрес учня для сторінки «Я». Остання відповідь сервера зберігається в IndexedDB, тож без
 * мережі сторінка показує останні відомі дані (принцип 1). Без опитування: дані беруться при
 * відкритті сторінки, бо змінюються лише після синхронізації.
 */
export function useStudentProgress() {
  const studentId = useAppSelector((s) => s.auth.session?.user.id)
  const query = useStudentProgressQuery(studentId ?? skipToken, { refetchOnMountOrArgChange: true })

  const cached = useLiveQuery(
    async () => {
      if (!studentId) return null
      const record = await db.meta.get(cacheKey(studentId))
      return (record?.value as StudentProgress | undefined) ?? null
    },
    [studentId],
  )

  useEffect(() => {
    if (!studentId || !query.data) return
    void db.meta.put({ key: cacheKey(studentId), value: query.data }).catch(() => undefined)
  }, [studentId, query.data])

  return {
    progress: query.data ?? cached ?? null,
    isLoading: query.isLoading && !cached,
    /** Сервер не відповів: показано збережені дані (або нічого) */
    isOffline: query.isError,
  }
}
