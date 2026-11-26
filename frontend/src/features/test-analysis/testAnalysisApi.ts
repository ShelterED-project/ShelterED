import { baseApi } from '@/shared/api/baseApi'

// AI-аналіз тесту класу (docs/test-analysis.md, контракт B1–B5). `result` — відповідь AI-сервісу
// зі справжніми id учнів; backend лише додає students[].feedback_edited.

export type AnalysisStatus = 'processing' | 'draft' | 'published' | 'failed'
export type SkillStatus = 'ok' | 'attention' | 'critical'
export type StudentLevel = 'strong' | 'ok' | 'needs_support'

export interface AnalysisFeedback {
  teacher: string
  student: string
  parent: string
}

export interface AnalysisStudent {
  student_id: string
  score_pct: number
  passed: boolean
  status: StudentLevel
  correct_question_ids: string[]
  wrong_question_ids: string[]
  strong_skills: string[]
  weak_skills: string[]
  misconception_ids: string[]
  feedback: AnalysisFeedback
  feedback_edited: boolean
}

export interface AnalysisSkill {
  skill: string
  status: SkillStatus
  correct_pct: number
  question_ids: string[]
}

export interface AnalysisWrongAnswer {
  option_ids: string[]
  option_text: string
  count: number
  student_ids: string[]
}

export interface AnalysisQuestion {
  question_id: string
  position: number
  skill: string
  status: SkillStatus
  correct_pct: number
  correct_count: number
  answered_count: number
  wrong_answers: AnalysisWrongAnswer[]
}

export interface AnalysisMisconception {
  id: string
  title: string
  explanation: string
  share_pct: number
  student_ids: string[]
  question_ids: string[]
}

export interface AnalysisResult {
  class_summary: {
    students_total: number
    average_score_pct: number
    passed_count: number
    pass_score_pct: number
    needs_support_ids: string[]
    overview: string
    recommendations: string[]
  }
  skills: AnalysisSkill[]
  questions: AnalysisQuestion[]
  misconceptions: AnalysisMisconception[]
  students: AnalysisStudent[]
  /** false — AI-модель не відповіла, тексти зібрано за шаблоном */
  llm_used: boolean
}

export interface TestAnalysis {
  id: string
  class_id: string
  test_id: string
  status: AnalysisStatus
  /** Зараховані спроби класу на момент запуску */
  attempts_count: number
  created_at: string
  created_by: string | null
  completed_at: string | null
  published_at: string | null
  /** Лише при failed: AI_UNAVAILABLE / AI_BAD_REQUEST / AI_TIMEOUT */
  error: { code: string } | null
  /** null, поки processing чи failed */
  result: AnalysisResult | null
}

export interface TestFeedbackItem {
  analysis_id: string
  test_id: string
  test_title: string
  lesson_title: string
  subject: string | null
  score_pct: number | null
  correct_count: number
  questions_total: number
  /** Учню — текст для учня, батькам — для батьків (Markdown) */
  text: string
  published_at: string
}

export interface TestFeedback {
  items: TestFeedbackItem[]
}

interface TestRef {
  classId: string
  testId: string
}

/** Правка тексту: поле відсутнє — без змін, null — повернути текст AI. */
export interface FeedbackEdit {
  student?: string | null
  parent?: string | null
}

export const testAnalysisApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** B2: останній аналіз тесту; 404 ANALYSIS_NOT_FOUND — ще не аналізували */
    testAnalysis: build.query<TestAnalysis, TestRef>({
      query: ({ classId, testId }) => `/classes/${classId}/tests/${testId}/analysis`,
    }),
    /** B1: запустити аналіз (202 — новий, 200 — уже йде) */
    startTestAnalysis: build.mutation<TestAnalysis, TestRef>({
      query: ({ classId, testId }) => ({ url: `/classes/${classId}/tests/${testId}/analysis`, method: 'POST' }),
      async onQueryStarted(ref, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }))
        if (data) void dispatch(testAnalysisApi.util.upsertQueryData('testAnalysis', ref, data))
      },
    }),
    /** B3: правка тексту для учня/батьків (лише чернетка) */
    editTestFeedback: build.mutation<
      { student_id: string; feedback: AnalysisFeedback; feedback_edited: boolean },
      TestRef & { analysisId: string; studentId: string; body: FeedbackEdit }
    >({
      query: ({ analysisId, studentId, body }) => ({
        url: `/test-analyses/${analysisId}/students/${studentId}`,
        method: 'PATCH',
        body,
      }),
      async onQueryStarted({ classId, testId, studentId }, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }))
        if (!data) return
        dispatch(
          testAnalysisApi.util.updateQueryData('testAnalysis', { classId, testId }, (draft) => {
            const entry = draft.result?.students.find((s) => s.student_id === studentId)
            if (entry) {
              entry.feedback = data.feedback
              entry.feedback_edited = data.feedback_edited
            }
          }),
        )
      },
    }),
    /** B4: опублікувати учням і батькам */
    publishTestAnalysis: build.mutation<TestAnalysis, TestRef & { analysisId: string }>({
      query: ({ analysisId }) => ({ url: `/test-analyses/${analysisId}/publish`, method: 'POST' }),
      async onQueryStarted({ classId, testId }, { dispatch, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }))
        if (data) void dispatch(testAnalysisApi.util.upsertQueryData('testAnalysis', { classId, testId }, data))
      },
    }),
    /** B5: опубліковані відгуки для учня (свій id) або батьків (id дитини) */
    testFeedback: build.query<TestFeedback, string>({
      query: (studentId) => `/students/${studentId}/test-feedback`,
    }),
  }),
})

export const {
  useTestAnalysisQuery,
  useStartTestAnalysisMutation,
  useEditTestFeedbackMutation,
  usePublishTestAnalysisMutation,
  useTestFeedbackQuery,
} = testAnalysisApi
