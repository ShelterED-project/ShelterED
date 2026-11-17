import { skipToken } from '@reduxjs/toolkit/query/react'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import { useStudentRollCallQuery } from '@/features/roll-call/rollCallApi'
import type { StudentRollCall } from '@/features/roll-call/rollCallApi'
import { useKnowledgeMapQuery, useStudentProgressQuery } from '@/features/student/studentApi'
import type { KnowledgeMap, StudentProgress } from '@/features/student/studentApi'
import { useCached } from '@/shared/db/useCached'
import { useChildWellbeingQuery } from './parentApi'

/** Перекличка змінюється лише під час тривоги; частіше питати немає сенсу (енергоменеджер). */
const ROLLCALL_POLL_MS = 30_000

/**
 * Дані кабінету батьків про одну дитину. Прогрес, мапа знань і остання відмітка переклички
 * кешуються в IndexedDB: без мережі батьки бачать останнє відоме (з часом, на який воно
 * актуальне). Зведення «Як ти зараз?» не кешуємо: це чутливі дані, лише свіжа відповідь.
 */
export function useChildDashboard(childId: string | null) {
  const arg = childId ?? skipToken
  const progressQuery = useStudentProgressQuery(arg, { refetchOnMountOrArgChange: true })
  const mapQuery = useKnowledgeMapQuery(arg, { refetchOnMountOrArgChange: true })
  const rollCallQuery = useStudentRollCallQuery(arg, {
    refetchOnMountOrArgChange: true,
    pollingInterval: ROLLCALL_POLL_MS,
    skipPollingIfUnfocused: true,
  })
  const { alert, isOffline: alertOffline } = useActiveAlert()

  const progress = useCached<StudentProgress>(childId ? `child_progress:${childId}` : null, progressQuery.data)
  const knowledgeMap = useCached<KnowledgeMap>(childId ? `child_map:${childId}` : null, mapQuery.data)
  const rollCall = useCached<StudentRollCall>(childId ? `child_rollcall:${childId}` : null, rollCallQuery.data)

  return {
    progress,
    knowledgeMap,
    rollCall,
    alert,
    /** Коли сервер востаннє відповів про перекличку (мс), null — ще ні разу в цій сесії */
    rollCallUpdatedAt: rollCallQuery.fulfilledTimeStamp ?? null,
    isLoading: progress === null && progressQuery.isLoading,
    isOffline: progressQuery.isError || rollCallQuery.isError || alertOffline,
  }
}

/** Тижневе зведення «Як ти зараз?» дитини (лише онлайн, див. useChildDashboard). */
export function useChildWellbeing(childId: string | null) {
  const query = useChildWellbeingQuery(childId ?? skipToken, { refetchOnMountOrArgChange: true })
  return { wellbeing: query.data ?? null, isLoading: query.isLoading, isOffline: query.isError }
}
