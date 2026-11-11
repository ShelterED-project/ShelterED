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

// Розклад класу. Час — місцевий час школи й UTC (для «зараз» порівнюємо UTC).

export interface ScheduleItem {
  kind: 'regular' | 'replaced' | 'extra'
  slot_id: string | null
  override_id: string | null
  subject_id: string
  /** HH:MM:SS, місцевий час школи; null лише в додаткового уроку без часу */
  starts_at: string | null
  ends_at: string | null
  starts_at_utc: string | null
  ends_at_utc: string | null
  /** Призначений на цю дату урок, якщо є */
  lesson_id: string | null
}

export interface ClassSchedule {
  class_id: string
  timezone: string
  days: { date: string; items: ScheduleItem[] }[]
}

export interface Subject {
  id: string
  /** null — загальний довідник */
  school_id: string | null
  name: string
}

export interface LessonSummary {
  id: string
  subject_id: string
  author_id: string
  title: string
  status: 'draft' | 'published'
  version: number
  published_at: string | null
  grade: number | null
  updated_at: string
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
    /** Розклад з сьогоднішнього дня (дата школи визначається на сервері), days 1..14 */
    classSchedule: build.query<ClassSchedule, { classId: string; days: number }>({
      query: ({ classId, days }) => `/classes/${classId}/schedule?days=${days}`,
    }),
    subjects: build.query<Subject[], void>({
      query: () => '/subjects',
    }),
    /** Уроки вчителя: свої чернетки й опубліковані */
    lessons: build.query<LessonSummary[], void>({
      query: () => '/lessons',
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
  useClassScheduleQuery,
  useSubjectsQuery,
  useLessonsQuery,
} = teacherApi
