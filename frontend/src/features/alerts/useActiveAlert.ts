import { useActiveAlertsQuery } from './alertsApi'
import type { Alert } from './alertsApi'

/** Як часто питаємо, чи є тривога. Лише поки вкладка у фокусі (енергоменеджер). */
const POLL_MS = 15_000

/**
 * Активна тривога користувача. Запасний шлях без push: клієнт сам питає сервер.
 * Без мережі лишається останній відомий стан, isOffline = true.
 */
export function useActiveAlert(): { alert: Alert | null; isOffline: boolean; refresh: () => void } {
  const { data, isError, refetch } = useActiveAlertsQuery(undefined, {
    pollingInterval: POLL_MS,
    skipPollingIfUnfocused: true,
  })
  const alert = data?.alerts.find((item) => item.ended_at === null) ?? null
  return { alert, isOffline: isError, refresh: () => void refetch() }
}
