import { baseApi } from '@/shared/api/baseApi'

export interface KnowledgeMapSubject {
  subject_id: string
  name: string
  lessons_total: number
  lessons_completed: number
  avg_score: number | null
  /** Предмет із прогалиною: тест не складено або вікно спливло */
  is_gap: boolean
}

export interface KnowledgeMap {
  student_id: string
  subjects: KnowledgeMapSubject[]
}

export const studentApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    knowledgeMap: build.query<KnowledgeMap, string>({
      query: (studentId) => `/students/${studentId}/knowledge-map`,
    }),
  }),
})

export const { useKnowledgeMapQuery } = studentApi
