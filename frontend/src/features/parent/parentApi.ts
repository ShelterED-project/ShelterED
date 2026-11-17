import { baseApi } from '@/shared/api/baseApi'

/** Дитина, привʼязана до батьків (GET /parent/children). */
export interface ParentChild {
  child_id: string
  display_name: string
  last_name: string | null
  /** null — дитина ще не в класі */
  class_id: string | null
  class_name: string | null
}

export type WellbeingMood = 'sunny' | 'cloudy' | 'hard'

/**
 * «Як ти зараз?» для батьків (docs/wellbeing-checkin.md): лише тижневе зведення словами,
 * без днів і чисел. Це не діагноз і не оцінка стану.
 */
export interface WellbeingParent {
  view: 'parent'
  student_id: string
  week_from: string
  week_to: string
  /** Більшість днів тижня; null — замало відповідей */
  mood: WellbeingMood | null
  summary: string
  /** Мʼякий рядок, коли кілька днів були непрості */
  gentle_note: string | null
  /** Поради для розмови (лише разом із gentle_note) */
  tips: string[]
}

export const parentApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    parentChildren: build.query<ParentChild[], void>({
      query: () => '/parent/children',
      providesTags: ['Children'],
    }),
    childWellbeing: build.query<WellbeingParent, string>({
      query: (childId) => `/students/${childId}/wellbeing`,
    }),
  }),
})

export const { useParentChildrenQuery, useChildWellbeingQuery } = parentApi
