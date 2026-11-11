import { skipToken } from '@reduxjs/toolkit/query/react'
import { useClassesQuery, useClassGapsQuery, useClassProgressQuery, useClassTestsQuery } from './teacherApi'

/**
 * Як часто оновлюємо результати класу. Агрегати перераховуються на сервері після синхронізації
 * учня, частіше питати немає сенсу. Лише поки вкладка у фокусі (енергоменеджер).
 */
const POLL_MS = 60_000
const polling = { pollingInterval: POLL_MS, skipPollingIfUnfocused: true }

/** Прогалини першого класу вчителя (для картки на огляді). */
export function useClassGaps() {
  const classes = useClassesQuery()
  const classId = classes.data?.[0]?.id
  const gaps = useClassGapsQuery(classId ?? skipToken, polling)
  return {
    gaps: gaps.data ?? null,
    isLoading: classes.isLoading || gaps.isLoading,
    isOffline: classes.isError || gaps.isError,
  }
}

/** Усі результати першого класу вчителя: прогрес по уроках, тести, прогалини (сторінка «Мапа класу»). */
export function useClassResults() {
  const classes = useClassesQuery()
  const teacherClass = classes.data?.[0]
  const arg = teacherClass?.id ?? skipToken
  const progress = useClassProgressQuery(arg, polling)
  const tests = useClassTestsQuery(arg, polling)
  const gaps = useClassGapsQuery(arg, polling)
  return {
    teacherClass,
    progress: progress.data ?? null,
    tests: tests.data ?? null,
    gaps: gaps.data ?? null,
    isLoading: classes.isLoading || progress.isLoading || tests.isLoading || gaps.isLoading,
    isOffline: classes.isError || progress.isError || tests.isError || gaps.isError,
  }
}
