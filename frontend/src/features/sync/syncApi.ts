import { baseApi } from '@/shared/api/baseApi'
import type { WireEvent } from '@/shared/db/types'

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

export const syncApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    postSyncEvents: build.mutation<SyncEventsResponse, SyncEventsRequest>({
      query: (body) => ({ url: '/sync/events', method: 'POST', body }),
    }),
  }),
})
