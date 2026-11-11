import { baseApi } from '@/shared/api/baseApi'
import type { LessonSummary } from './teacherApi'

// Авторинг уроків вчителем (B5.3). Усі id створює клієнт (принцип 2): повтор того самого запиту
// з тими самими даними повертає 200 і нічого не дублює, з іншими — 409 ID_CONFLICT.
// Опублікований урок лише для читання (409 LESSON_PUBLISHED): спершу зняти з публікації.

export type ModulePart = 'shelter' | 'main'
export type QuestionKind = 'single' | 'multiple'

export interface CardOut {
  id: string
  module_id: string
  position: number
  kind: 'text' | 'image' | 'video'
  /** Текстова картка: { text } (так само читає її учень з пакета) */
  body: Record<string, unknown>
  media_asset_id: string | null
}

export interface ModuleOut {
  id: string
  lesson_id: string
  part: ModulePart
  position: number
  title: string
  duration_min: number
  cards: CardOut[]
}

export interface QuestionOption {
  id: string
  text: string
}

export interface QuestionOut {
  id: string
  test_id: string
  position: number
  kind: QuestionKind
  prompt: string
  options: QuestionOption[]
  answer_key: string[]
  points: number
}

export interface TestOut {
  id: string
  lesson_id: string
  title: string
  window_enabled: boolean
  window_hours: 24 | 48 | 72 | null
  questions: QuestionOut[]
}

export interface LessonOut extends LessonSummary {
  shelter_part: string
  main_part: string
  /** Спершу модулі укриття, потім основні, кожні за position */
  modules: ModuleOut[]
  tests: TestOut[]
  size_bytes: number
}

export interface LessonFields {
  subject_id: string
  title: string
  shelter_part: string
  main_part: string
  grade: number | null
}

/** Тіло помилки бекенду: { error: { code, message, details } } */
export interface ApiError {
  status: number | string
  data?: { error?: { code?: string; message?: string; details?: unknown } }
}

const lessonTag = (id: string) => [{ type: 'Lesson' as const, id }, 'LessonList' as const]

export const lessonEditorApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    lesson: build.query<LessonOut, string>({
      query: (id) => `/lessons/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Lesson', id }],
    }),
    createLesson: build.mutation<LessonOut, LessonFields & { id: string }>({
      query: (body) => ({ url: '/lessons', method: 'POST', body }),
      invalidatesTags: ['LessonList'],
    }),
    updateLesson: build.mutation<LessonOut, { id: string; patch: Partial<LessonFields> }>({
      query: ({ id, patch }) => ({ url: `/lessons/${id}`, method: 'PATCH', body: patch }),
      invalidatesTags: (_result, _error, { id }) => lessonTag(id),
    }),
    deleteLesson: build.mutation<void, string>({
      query: (id) => ({ url: `/lessons/${id}`, method: 'DELETE' }),
      invalidatesTags: ['LessonList'],
    }),

    createModule: build.mutation<
      ModuleOut,
      { lessonId: string; id: string; part: ModulePart; position: number; title: string; duration_min: number }
    >({
      query: ({ lessonId, ...body }) => ({ url: `/lessons/${lessonId}/modules`, method: 'POST', body }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    deleteModule: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/modules/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),

    createCard: build.mutation<CardOut, { lessonId: string; moduleId: string; id: string; position: number; text: string }>({
      query: ({ moduleId, id, position, text }) => ({
        url: `/modules/${moduleId}/cards`,
        method: 'POST',
        body: { id, position, kind: 'text', body: { text } },
      }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    updateCard: build.mutation<CardOut, { lessonId: string; id: string; text: string }>({
      query: ({ id, text }) => ({ url: `/cards/${id}`, method: 'PATCH', body: { body: { text } } }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    deleteCard: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/cards/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),

    createTest: build.mutation<
      TestOut,
      { lessonId: string; id: string; title: string; window_enabled: boolean; window_hours: 24 | 48 | 72 | null }
    >({
      query: ({ lessonId, ...body }) => ({ url: `/lessons/${lessonId}/tests`, method: 'POST', body }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    deleteTest: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/tests/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),

    createQuestion: build.mutation<
      QuestionOut,
      {
        lessonId: string
        testId: string
        id: string
        position: number
        kind: QuestionKind
        prompt: string
        options: QuestionOption[]
        answer_key: string[]
        points: number
      }
    >({
      query: ({ lessonId: _lessonId, testId, ...body }) => ({ url: `/tests/${testId}/questions`, method: 'POST', body }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    deleteQuestion: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/questions/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),

    // Публікація: сервер перевіряє урок (422 LESSON_NOT_PUBLISHABLE зі списком проблем) і
    // перезбирає пакети класів, де урок уже стоїть у розкладі. Обидві дії ідемпотентні.
    publishLesson: build.mutation<LessonOut, string>({
      query: (id) => ({ url: `/lessons/${id}/publish`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [...lessonTag(id), 'Schedule'],
    }),
    unpublishLesson: build.mutation<LessonOut, string>({
      query: (id) => ({ url: `/lessons/${id}/unpublish`, method: 'POST' }),
      invalidatesTags: (_result, _error, id) => [...lessonTag(id), 'Schedule'],
    }),

    // Призначення уроку на слот розкладу в конкретну дату (upsert, ідемпотентно).
    // Після нього сервер перезбирає пакет класу, і учень отримує урок при синхронізації пакетів.
    assignLesson: build.mutation<
      { slot_id: string; date: string; lesson_id: string; pack_day_bytes: number },
      { classId: string; slotId: string; date: string; lessonId: string }
    >({
      query: ({ classId, slotId, date, lessonId }) => ({
        url: `/classes/${classId}/schedule/slots/${slotId}/lessons/${date}`,
        method: 'PUT',
        body: { lesson_id: lessonId },
      }),
      invalidatesTags: ['Schedule'],
    }),
    unassignLesson: build.mutation<void, { classId: string; slotId: string; date: string }>({
      query: ({ classId, slotId, date }) => ({
        url: `/classes/${classId}/schedule/slots/${slotId}/lessons/${date}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Schedule'],
    }),
  }),
})

export const {
  useLessonQuery,
  useCreateLessonMutation,
  useUpdateLessonMutation,
  useDeleteLessonMutation,
  useCreateModuleMutation,
  useDeleteModuleMutation,
  useCreateCardMutation,
  useUpdateCardMutation,
  useDeleteCardMutation,
  useCreateTestMutation,
  useDeleteTestMutation,
  useCreateQuestionMutation,
  useDeleteQuestionMutation,
  usePublishLessonMutation,
  useUnpublishLessonMutation,
  useAssignLessonMutation,
  useUnassignLessonMutation,
} = lessonEditorApi

/** Наступна вільна позиція в групі: сервер не перенумеровує, зайнята дає 409 POSITION_TAKEN. */
export function nextPosition(items: { position: number }[]): number {
  return items.reduce((max, item) => Math.max(max, item.position + 1), 0)
}

/** Зрозуміле вчителю повідомлення з помилки бекенду. */
export function errorMessage(error: unknown): string {
  const e = error as ApiError
  const code = e?.data?.error?.code
  switch (code) {
    case 'LESSON_NOT_PUBLISHABLE':
      return publishProblems(e.data?.error?.details)
    case 'LESSON_NOT_PUBLISHED':
      return 'Спершу опублікуйте урок, потім призначайте його в розклад.'
    case 'LESSON_SUBJECT_MISMATCH':
      return 'Предмет уроку не збігається з предметом цього слоту розкладу.'
    case 'SLOT_CANCELLED':
      return 'Цей урок у розкладі скасовано, на нього не можна призначити.'
    case 'INVALID_SCHEDULE':
      return 'Цей слот не діє в обрану дату.'
    case 'PACK_DAY_LIMIT_EXCEEDED':
      return 'Пакет цього дня завеликий для телефонів учнів. Оберіть інший день або зменште урок.'
    case 'LESSON_PUBLISHED':
      return 'Урок опубліковано, його не можна змінювати. Спершу зніміть його з публікації.'
    case 'IN_USE':
    case 'LESSON_IN_USE':
      return 'Учні вже проходили цей матеріал або урок стоїть у розкладі, тому видалити його не можна.'
    case 'POSITION_TAKEN':
      return 'Це місце вже зайняте. Оновіть сторінку й спробуйте ще раз.'
    case 'ID_CONFLICT':
      return 'Конфлікт даних. Оновіть сторінку й спробуйте ще раз.'
    case 'FORBIDDEN':
      return 'Змінювати урок може лише його автор.'
  }
  if (e?.status === 422) return 'Перевірте поля: щось заповнено неправильно.'
  if (e?.status === 'FETCH_ERROR') return 'Немає звʼязку з сервером. Перевірте мережу й спробуйте ще раз.'
  return e?.data?.error?.message ?? 'Не вдалося зберегти. Спробуйте ще раз.'
}

/** Перевірки публікації, які не пройшли (details помилки LESSON_NOT_PUBLISHABLE). */
function publishProblems(details: unknown): string {
  const checks = Array.isArray(details) ? details.map((d) => (d as { check?: string }).check) : []
  const text: Record<string, string> = {
    shelter_part: 'заповніть «Текст для укриття»',
    video_subtitles: 'додайте субтитри до відео',
    lesson_size: 'урок завеликий для телефонів учнів',
    pack_day_size: 'пакет дня, де стоїть урок, завеликий',
  }
  const reasons = checks.map((c) => (c && text[c]) || 'урок не пройшов перевірку')
  return `Урок не можна опублікувати: ${[...new Set(reasons)].join('; ')}.`
}
