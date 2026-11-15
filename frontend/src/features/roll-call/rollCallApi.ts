import { baseApi } from '@/shared/api/baseApi'

export interface StudentRollCall {
  /** null, якщо активної переклички немає */
  session_id: string | null
  student_id?: string | null
  status?: 'safe' | 'in_shelter' | null
  is_drill?: boolean | null
  opened_at?: string | null
  occurred_at?: string | null
  received_at?: string | null
}

export const rollCallApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    studentRollCall: build.query<StudentRollCall, string>({
      query: (studentId) => `/students/${studentId}/rollcall/current`,
    }),
  }),
})

export const { useStudentRollCallQuery } = rollCallApi
