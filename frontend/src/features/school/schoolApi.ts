import { baseApi } from '@/shared/api/baseApi'

// Учні класу для вчителя класу й адміна школи: список, скидання PIN, код привʼязки батьків.

export interface ClassStudent {
  student_id: string
  display_name: string
  last_name: string | null
}

export interface ParentLinkCode {
  /** Одноразовий код, батьки вводять його в кабінеті */
  code: string
  expires_at: string
}

export const schoolApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    classStudents: build.query<ClassStudent[], string>({
      query: (classId) => `/classes/${classId}/students`,
    }),
    // Наступний вхід учня задасть новий PIN; усі його сесії перестають діяти.
    resetStudentPin: build.mutation<void, { classId: string; studentId: string }>({
      query: ({ classId, studentId }) => ({
        url: `/classes/${classId}/students/${studentId}/pin-reset`,
        method: 'POST',
      }),
    }),
    // Кожен виклик видає новий код (7 днів); попередні коди лишаються дійсними до терміну.
    createParentLinkCode: build.mutation<ParentLinkCode, string>({
      query: (studentId) => ({ url: `/students/${studentId}/parent-link-codes`, method: 'POST' }),
    }),
  }),
})

export const { useClassStudentsQuery, useResetStudentPinMutation, useCreateParentLinkCodeMutation } = schoolApi
