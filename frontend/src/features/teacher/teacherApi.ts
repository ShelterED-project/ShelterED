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

// Результати класу (кабінет B14). Сервер віддає агрегати, які перераховує Celery після
// кожного пакета синхронізації учня, тож дані можуть відставати на кілька секунд.

export interface ClassLessonProgress {
  lesson_id: string
  title: string
  subject_name: string
  /** Перша дата уроку в розкладі класу */
  first_date: string
  students_total: number
  /** Учні, що завершили всі модулі уроку */
  students_completed: number
  avg_progress_pct: number
  /** Пари (учень, тест уроку) із зарахованою спробою */
  tests_scored: number
  tests_passed: number
  avg_score: number | null
}

export interface ClassProgress {
  class_id: string
  computed_at: string | null
  lessons: ClassLessonProgress[]
}

export type TestResultStatus = 'passed' | 'not_passed' | 'closing_soon' | 'pending'

export interface StudentTestResult {
  student_id: string
  display_name: string
  last_name: string | null
  status: TestResultStatus
  score: number | null
  attempts: number
  /** Кінець вікна тесту; null — тест без вікна або урок ще не завершено */
  deadline: string | null
  /** Час пристрою підозрілий — варто перевірити (не блокується) */
  is_suspicious: boolean
}

export interface ClassTest {
  test_id: string
  lesson_id: string
  lesson_title: string
  title: string
  window_hours: number | null
  counts: Record<TestResultStatus, number>
  students: StudentTestResult[]
}

export interface ClassTests {
  class_id: string
  /** Поріг «склав», % */
  pass_score: number
  tests: ClassTest[]
}

export interface GapQuestion {
  question_id: string
  test_id: string
  prompt: string
  answered: number
  correct: number
  correct_pct: number
}

export interface GapTopic {
  lesson_id: string
  title: string
  subject_name: string
  avg_score: number | null
  tests_scored: number
  tests_passed: number
  /** Середня оцінка класу нижча за поріг «склав» */
  is_gap: boolean
  /** Від найгірше засвоєного */
  questions: GapQuestion[]
}

export interface ClassGaps {
  class_id: string
  pass_score: number
  /** Тема = урок; від найнижчої середньої оцінки */
  topics: GapTopic[]
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
    classProgress: build.query<ClassProgress, string>({
      query: (classId) => `/classes/${classId}/progress`,
    }),
    classTests: build.query<ClassTests, string>({
      query: (classId) => `/classes/${classId}/tests`,
    }),
    classGaps: build.query<ClassGaps, string>({
      query: (classId) => `/classes/${classId}/gaps`,
    }),
  }),
})

export const {
  useClassesQuery,
  useClassRollCallQuery,
  useStartRollCallMutation,
  useCloseRollCallMutation,
  useClassProgressQuery,
  useClassTestsQuery,
  useClassGapsQuery,
} = teacherApi
