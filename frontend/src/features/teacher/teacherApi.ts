import { baseApi } from '@/shared/api/baseApi'
import { generateId } from '@/shared/lib/uuid'

export interface ClassOut {
  id: string
  name: string
  grade: number
  school_id: string
  academic_year: string
  join_code: string
  teacher_ids: string[]
}

export type StudentRollCallStatus = 'safe' | 'in_shelter' | 'no_response'

export interface RollCallStudent {
  student_id: string
  display_name: string
  last_name: string | null
  status: StudentRollCallStatus
  occurred_at: string | null
  received_at: string | null
}

export interface RollCallSession {
  id: string
  class_id: string
  alert_event_id: string | null
  is_drill: boolean
  opened_at: string
  closed_at: string | null
  summary: { safe: number; in_shelter: number; no_response: number }
  students: RollCallStudent[]
}

export interface ClassRollCall {
  class_id: string
  /** null, якщо переклички немає */
  session: RollCallSession | null
}

export const teacherApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    classes: build.query<ClassOut[], void>({
      query: () => '/classes',
    }),
    classRollCall: build.query<ClassRollCall, string>({
      query: (classId) => `/classes/${classId}/rollcall/current`,
    }),
    // id сесії створює клієнт (UUID), повтор із тим самим id нічого не дублює.
    startRollCall: build.mutation<RollCallSession, { classId: string; isDrill: boolean }>({
      query: ({ classId, isDrill }) => ({
        url: `/classes/${classId}/rollcall`,
        method: 'POST',
        body: { id: generateId(), is_drill: isDrill },
      }),
    }),
    closeRollCall: build.mutation<RollCallSession, { classId: string; sessionId: string }>({
      query: ({ classId, sessionId }) => ({
        url: `/classes/${classId}/rollcall/${sessionId}/close`,
        method: 'POST',
      }),
    }),
  }),
})

export const {
  useClassesQuery,
  useClassRollCallQuery,
  useStartRollCallMutation,
  useCloseRollCallMutation,
} = teacherApi
