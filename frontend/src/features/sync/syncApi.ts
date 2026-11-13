import { baseApi } from '@/shared/api/baseApi'
import type { CreditStatus, WireEvent } from '@/shared/db/types'

export interface SyncEventsRequest {
  /** Поточний час пристрою в момент відправки: сервер рахує зсув годинника */
  sent_at: string
  /** Від 1 до 100 подій */
  events: WireEvent[]
}

export interface SyncEventResult {
  client_event_id: string
  status: 'accepted' | 'duplicate' | 'rejected'
  reason?: string | null
}

export interface SyncEventsResponse {
  results: SyncEventResult[]
  server_time: string
}

// Стрічка змін (GET /sync/changes): актуальний стан рядків поточного учня після курсора.
// Кожен елемент — стан, а не історія: той самий рядок може прийти знову з новим станом.

export interface AttemptResultChange {
  kind: 'attempt_result'
  client_event_id: string
  test_id: string
  credit_status: CreditStatus
  /** 0..100; null, поки не оцінено */
  score: number | null
  is_suspicious: boolean
}

export interface ModuleProgressChange {
  kind: 'module_progress'
  module_id: string
  /** Підсумковий максимум прогресу модуля */
  progress_pct: number
  completed_at: string | null
}

export interface RollCallStatusChange {
  kind: 'rollcall_status'
  session_id: string
  status: 'safe' | 'in_shelter'
  occurred_at: string
}

export type SyncChange = AttemptResultChange | ModuleProgressChange | RollCallStatusChange

export interface SyncChangesResponse {
  changes: SyncChange[]
  /** Передати в наступний запит як cursor; без змін дорівнює вхідному */
  next_cursor: string
  has_more: boolean
}

export const syncApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    postSyncEvents: build.mutation<SyncEventsResponse, SyncEventsRequest>({
      query: (body) => ({ url: '/sync/events', method: 'POST', body }),
    }),
    syncChanges: build.query<SyncChangesResponse, string | null>({
      query: (cursor) => (cursor ? `/sync/changes?cursor=${encodeURIComponent(cursor)}` : '/sync/changes'),
    }),
  }),
})
