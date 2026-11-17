import { useState } from 'react'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import type { Alert } from '@/features/alerts/alertsApi'
import { useClassesQuery } from '@/features/teacher/teacherApi'
import { useAlertJournalQuery, useSchoolRollCallsQuery, useSchoolUsersQuery } from './adminApi'

/** Під час тривоги перекличка змінюється щохвилини; без тривоги не опитуємо (енергоменеджер). */
const ROLLCALL_POLL_MS = 15_000
const DAY_MS = 24 * 60 * 60 * 1000

/** Дата «2026-11-17» за Києвом: журнал тривог фільтрується за київськими датами. */
export function kyivDate(date: Date): string {
  return date.toLocaleDateString('sv-SE', { timeZone: 'Europe/Kyiv' })
}

/** Тривалість тривоги в хвилинах; незакінчена — до цього моменту. */
export function alertMinutes(alert: Alert, now = Date.now()): number {
  const end = alert.ended_at ? new Date(alert.ended_at).getTime() : now
  return Math.max(0, Math.round((end - new Date(alert.started_at).getTime()) / 60_000))
}

/**
 * Дані огляду адміністрації: класи, вчителі, активна тривога, перекличка по класах і тривоги
 * за тиждень. Дані лише з памʼяті RTK Query, як у кабінеті вчителя: без мережі видно останні
 * отримані за цей сеанс.
 */
export function useSchoolOverview() {
  const classes = useClassesQuery(undefined, { refetchOnMountOrArgChange: true })
  const teachers = useSchoolUsersQuery('teacher')
  const { alert, isOffline: alertOffline } = useActiveAlert()

  const classIds = (classes.data ?? []).map((c) => c.id)
  const rollCalls = useSchoolRollCallsQuery(classIds, {
    skip: classIds.length === 0,
    refetchOnMountOrArgChange: true,
    pollingInterval: alert ? ROLLCALL_POLL_MS : 0,
    skipPollingIfUnfocused: true,
  })

  // Тиждень рахуємо від відкриття сторінки, а не на кожен рендер.
  const [week] = useState(() => {
    const now = Date.now()
    return { from: kyivDate(new Date(now - 6 * DAY_MS)), to: kyivDate(new Date(now)) }
  })
  const journal = useAlertJournalQuery(week)

  const sessions = (rollCalls.data ?? []).flatMap((r) => (r.session ? [r.session] : []))
  const shelter = sessions.reduce(
    (sum, s) => ({
      inShelter: sum.inShelter + s.summary.in_shelter,
      safe: sum.safe + s.summary.safe,
      total: sum.total + s.summary.in_shelter + s.summary.safe + s.summary.no_response,
    }),
    { inShelter: 0, safe: 0, total: 0 },
  )

  return {
    classes: classes.data ?? [],
    teachers: teachers.data ?? [],
    alert,
    rollCalls: rollCalls.data ?? [],
    /** Сума по відкритих перекличках класів */
    shelter,
    hasRollCall: sessions.length > 0,
    weekAlerts: journal.data ?? [],
    isLoading: classes.isLoading,
    isOffline: classes.isError || alertOffline || rollCalls.isError,
  }
}
