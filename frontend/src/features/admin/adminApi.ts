import type { Alert } from '@/features/alerts/alertsApi'
import type { ClassOut, ClassRollCall } from '@/features/teacher/teacherApi'
import { baseApi } from '@/shared/api/baseApi'
import { generateId } from '@/shared/lib/uuid'

export type ListedRole = 'teacher' | 'admin' | 'student'

/** Користувач школи (GET /admin/users). Батьків у списку немає: вони не належать школі. */
export interface SchoolUser {
  id: string
  role: ListedRole
  display_name: string
  last_name: string | null
  school_id: string | null
}

export interface ClassFields {
  name: string
  grade: number
  /** «2026/2027» */
  academic_year: string
}

/** Локації школи для тривог: uid району, громади й міста зі словника alerts.in.ua; null — не вказано. */
export interface AlertLocations {
  alert_raion_uid: string | null
  alert_hromada_uid: string | null
  alert_city_uid: string | null
}

export interface SchoolAlertLocations extends AlertLocations {
  school_id: string
  /** Область (uid регіону alerts.in.ua); тут не змінюється */
  region_code: string
}

/** Найбільша сторінка /admin/users і /alerts на бекенді. */
const PAGE_LIMIT = 200

export const adminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    schoolUsers: build.query<SchoolUser[], ListedRole | undefined>({
      query: (role) => ({ url: '/admin/users', params: { limit: PAGE_LIMIT, ...(role ? { role } : {}) } }),
      providesTags: ['Users'],
    }),
    alertLocations: build.query<SchoolAlertLocations, string>({
      query: (schoolId) => `/schools/${schoolId}/alert-locations`,
      providesTags: ['School'],
    }),
    // PUT замінює всі три поля (null — очистити), тож повтор нічого не ламає.
    saveAlertLocations: build.mutation<SchoolAlertLocations, { schoolId: string } & AlertLocations>({
      query: ({ schoolId, ...body }) => ({ url: `/schools/${schoolId}/alert-locations`, method: 'PUT', body }),
      invalidatesTags: ['School'],
    }),
    // id класу створює клієнт (UUID): повторний запит не створить другий клас.
    createClass: build.mutation<ClassOut, ClassFields>({
      query: (body) => ({ url: '/classes', method: 'POST', body: { id: generateId(), ...body } }),
      invalidatesTags: ['Classes'],
    }),
    updateClass: build.mutation<ClassOut, { classId: string } & Partial<ClassFields>>({
      query: ({ classId, ...body }) => ({ url: `/classes/${classId}`, method: 'PATCH', body }),
      invalidatesTags: ['Classes'],
    }),
    // Видаляється лише клас без учнів (інакше 409 CLASS_NOT_EMPTY).
    deleteClass: build.mutation<void, string>({
      query: (classId) => ({ url: `/classes/${classId}`, method: 'DELETE' }),
      invalidatesTags: ['Classes'],
    }),
    // Старий код перестає діяти одразу.
    newJoinCode: build.mutation<ClassOut, { classId: string; expiresInDays?: number }>({
      query: ({ classId, expiresInDays }) => ({
        url: `/classes/${classId}/join-code`,
        method: 'POST',
        body: expiresInDays ? { expires_in_days: expiresInDays } : {},
      }),
      invalidatesTags: ['Classes'],
    }),
    setClassTeacher: build.mutation<void, { classId: string; teacherId: string; assigned: boolean }>({
      query: ({ classId, teacherId, assigned }) => ({
        url: `/classes/${classId}/teachers/${teacherId}`,
        method: assigned ? 'PUT' : 'DELETE',
      }),
      invalidatesTags: ['Classes'],
    }),
    /** Журнал тривог школи, від нових до старих. from і to — дати за Києвом, включно. */
    alertJournal: build.query<Alert[], { from: string; to: string }>({
      query: ({ from, to }) => ({ url: '/alerts', params: { from, to, limit: PAGE_LIMIT } }),
    }),
    /**
     * Поточна перекличка всіх класів школи одним запитом-обгорткою: загальношкільного
     * ендпоінта немає (B12.5), тож сумуємо по класах. Клас без звʼязку — просто без даних.
     */
    schoolRollCalls: build.query<ClassRollCall[], string[]>({
      async queryFn(classIds, _api, _extra, baseQuery) {
        const results = await Promise.all(classIds.map((id) => baseQuery(`/classes/${id}/rollcall/current`)))
        const failed = results.find((r) => r.error)
        if (failed?.error && results.every((r) => r.error)) return { error: failed.error }
        return { data: results.filter((r) => !r.error).map((r) => r.data as ClassRollCall) }
      },
    }),
  }),
})

export const {
  useSchoolUsersQuery,
  useAlertLocationsQuery,
  useSaveAlertLocationsMutation,
  useCreateClassMutation,
  useUpdateClassMutation,
  useDeleteClassMutation,
  useNewJoinCodeMutation,
  useSetClassTeacherMutation,
  useAlertJournalQuery,
  useSchoolRollCallsQuery,
} = adminApi
