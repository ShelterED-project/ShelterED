import { baseApi } from '@/shared/api/baseApi'
import { generateId } from '@/shared/lib/uuid'

export interface Alert {
  id: string
  region_code: string
  school_id: string | null
  /** Лише для ручної тривоги класу */
  class_id: string | null
  source: 'api' | 'manual'
  /** Тренувальна тривога */
  is_drill: boolean
  started_at: string
  /** Відбій; null, поки тривога триває */
  ended_at: string | null
}

export interface ActiveAlerts {
  alerts: Alert[]
  /** false: API тривог давно не відповідало, лишається ручна кнопка */
  source_available: boolean
}

export const alertsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    activeAlerts: build.query<ActiveAlerts, void>({
      query: () => '/alerts/active',
    }),
    // id тривоги створює клієнт (UUID): повторний запит не створить другу тривогу й не дублює push.
    startManualAlert: build.mutation<Alert, { classId: string; isDrill: boolean }>({
      query: ({ classId, isDrill }) => ({
        url: '/alerts/manual',
        method: 'POST',
        body: { id: generateId(), class_id: classId, is_drill: isDrill },
      }),
    }),
    endAlert: build.mutation<Alert, string>({
      query: (alertId) => ({ url: `/alerts/${alertId}/end`, method: 'POST' }),
    }),
  }),
})

export const { useActiveAlertsQuery, useStartManualAlertMutation, useEndAlertMutation } = alertsApi
