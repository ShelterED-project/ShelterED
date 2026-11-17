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

// Прогрес учня (B14): агрегати, які сервер перераховує після синхронізації подій.

export interface StudentLessonProgress {
  lesson_id: string
  title: string
  subject_name: string
  progress_pct: number
  modules_done: number
  modules_total: number
  /** Завершення уроку (годинник пристрою) */
  completed_at: string | null
  study_minutes: number
}

export type StudentTestStatus = 'passed' | 'not_passed' | 'closing_soon' | 'pending'

export interface StudentTest {
  test_id: string
  lesson_id: string
  title: string
  window_hours: number | null
  status: StudentTestStatus
  score: number | null
  attempts: number
  /** Кінець вікна тесту; null — тест без вікна або урок ще не завершено */
  deadline: string | null
}

export interface StudentProgress {
  student_id: string
  computed_at: string | null
  lessons: StudentLessonProgress[]
  tests: StudentTest[]
  /** Час навчання = плановий час завершених модулів; days — останні 7 днів, включно з сьогодні */
  study: { total_minutes: number; last_7_days_minutes: number; days: { day: string; minutes: number }[] }
}

export const studentApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    knowledgeMap: build.query<KnowledgeMap, string>({
      query: (studentId) => `/students/${studentId}/knowledge-map`,
    }),
    studentProgress: build.query<StudentProgress, string>({
      query: (studentId) => `/students/${studentId}/progress`,
    }),
  }),
})

export const { useKnowledgeMapQuery, useStudentProgressQuery } = studentApi
