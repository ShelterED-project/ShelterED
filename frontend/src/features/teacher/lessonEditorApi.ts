import { baseApi } from '@/shared/api/baseApi'
import type { LessonSummary } from './teacherApi'

// Авторинг уроків вчителем (B5.3). Усі id створює клієнт (принцип 2): повтор того самого запиту
// з тими самими даними повертає 200 і нічого не дублює, з іншими — 409 ID_CONFLICT.
// Опублікований урок лише для читання (409 LESSON_PUBLISHED): спершу зняти з публікації.
//
// Частина контракту ще будується на бекенді (позначено «ще будується»): попередження уроку,
// стискання відео на сервері (kind=video_source, processing_status) та імпорт з Wikimedia Commons.
// Поки ендпоінтів немає, інтерфейс працює без них (див. помилки 404 у errorMessage).

export type ModulePart = 'shelter' | 'main'
export type QuestionKind = 'single' | 'multiple' | 'text' | 'match'
export type CardKind = 'text' | 'image' | 'video'
export type MediaKind = 'video' | 'image' | 'subtitles'
/** Ще будується: стан обробки відео на сервері (`kind=video_source`). Без поля — файл готовий. */
export type ProcessingStatus = 'processing' | 'ready' | 'failed'

export interface MediaOut {
  id: string
  kind: MediaKind
  mime_type: string
  size_bytes: number
  sha256: string
  duration_s: number | null
  subtitles_id: string | null
  url: string
  /** Ще будується */
  processing_status?: ProcessingStatus | null
  /** Ще будується: автор і ліцензія файла з Wikimedia Commons */
  attribution?: string | null
  /** Ще будується: сторінка файла на Wikimedia Commons */
  source_url?: string | null
}

export interface CardMediaOut extends MediaOut {
  subtitles: MediaOut | null
}

export interface CardOut {
  id: string
  module_id: string
  position: number
  kind: CardKind
  /** Текстова картка: { text } (простий Markdown); медіа: { caption } */
  body: Record<string, unknown>
  media_asset_id: string | null
  /** Медіа з URL і субтитрами (лише у відповідях редактора) */
  media?: CardMediaOut | null
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

/** id варіантів (single/multiple), прийнятні відповіді (text) або {лівий: правий} (match) */
export type AnswerKey = string[] | Record<string, string>

export interface QuestionFields {
  kind: QuestionKind
  prompt: string
  options: QuestionOption[]
  right_options: QuestionOption[] | null
  answer_key: AnswerKey
  points: number
  explanation: string | null
}

export interface QuestionOut extends QuestionFields {
  id: string
  test_id: string
  position: number
}

export type WindowHours = 24 | 48 | 72

export interface TestOut {
  id: string
  lesson_id: string
  title: string
  window_enabled: boolean
  window_hours: WindowHours | null
  questions: QuestionOut[]
}

/** Перевірка публікації: помилка (блокує) чи попередження (не блокує). */
export interface LessonCheck {
  check: string
  message?: string
  module_id?: string | null
  card_id?: string | null
  test_id?: string | null
  question_id?: string | null
  media_asset_id?: string | null
  size_bytes?: number
  limit_bytes?: number
}

export interface LessonOut extends LessonSummary {
  shelter_part: string
  main_part: string
  /** Спершу модулі укриття, потім основні, кожні за position */
  modules: ModuleOut[]
  tests: TestOut[]
  size_bytes: number
  /** Ліміт розміру уроку й пакета дня */
  limit_bytes?: number
  copied_from_id?: string | null
  /** Ще будується: попередження, що не блокують публікацію (напр. відео без субтитрів) */
  warnings?: LessonCheck[]
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

// Окремо від решти: мутації нижче оновлюють кеш уроку через lessonQueryApi.util (оптимістично),
// а посилатися на власний результат injectEndpoints TypeScript не дає.
const lessonQueryApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    lesson: build.query<LessonOut, string>({
      query: (id) => `/lessons/${id}`,
      providesTags: (_result, _error, id) => [{ type: 'Lesson', id }],
    }),
  }),
})

type LessonRecipe = (lesson: LessonOut) => void
type Dispatcher = (action: ReturnType<typeof lessonQueryApi.util.updateQueryData>) => { undo: () => void }

/** Змінює урок у кеші одразу; при помилці запиту відкочує. */
async function optimistic(
  dispatch: Dispatcher,
  lessonId: string,
  recipe: LessonRecipe,
  queryFulfilled: Promise<unknown>,
): Promise<void> {
  const patch = dispatch(lessonQueryApi.util.updateQueryData('lesson', lessonId, recipe))
  try {
    await queryFulfilled
  } catch {
    patch.undo()
  }
}

/** Після успіху кладе відповідь сервера в кеш уроку без повторного завантаження. */
async function applyResult<T>(
  dispatch: Dispatcher,
  lessonId: string,
  queryFulfilled: Promise<{ data: T }>,
  recipe: (lesson: LessonOut, data: T) => void,
): Promise<void> {
  try {
    const { data } = await queryFulfilled
    dispatch(lessonQueryApi.util.updateQueryData('lesson', lessonId, (lesson) => recipe(lesson, data)))
  } catch {
    // Помилку показує той, хто викликав мутацію.
  }
}

function findCard(lesson: LessonOut, id: string): CardOut | undefined {
  for (const m of lesson.modules) {
    const card = m.cards.find((c) => c.id === id)
    if (card) return card
  }
  return undefined
}

function findQuestion(lesson: LessonOut, id: string): QuestionOut | undefined {
  for (const t of lesson.tests) {
    const q = t.questions.find((x) => x.id === id)
    if (q) return q
  }
  return undefined
}

/** Позиції 1..n у новому порядку: так їх ставить і сервер. */
function renumber<T extends { id: string; position: number }>(items: T[], ids: string[]): void {
  const order = new Map(ids.map((id, i) => [id, i + 1]))
  for (const item of items) {
    const pos = order.get(item.id)
    if (pos !== undefined) item.position = pos
  }
}

export interface CardCreateArgs {
  lessonId: string
  moduleId: string
  id: string
  position: number
  kind: CardKind
  body: Record<string, unknown>
  media_asset_id?: string | null
}

export const lessonEditorApi = lessonQueryApi.injectEndpoints({
  endpoints: (build) => ({
    createLesson: build.mutation<LessonOut, LessonFields & { id: string }>({
      query: (body) => ({ url: '/lessons', method: 'POST', body }),
      invalidatesTags: ['LessonList'],
    }),
    updateLesson: build.mutation<LessonOut, { id: string; patch: Partial<LessonFields> }>({
      query: ({ id, patch }) => ({ url: `/lessons/${id}`, method: 'PATCH', body: patch }),
      // Відповідь — урок повністю: кладемо в кеш без перезавантаження (автозбереження часте).
      onQueryStarted: async ({ id }, { dispatch, queryFulfilled }) => {
        try {
          const { data } = await queryFulfilled
          dispatch(lessonQueryApi.util.upsertQueryData('lesson', id, data))
        } catch {
          // Помилку показує поле.
        }
      },
      invalidatesTags: ['LessonList'],
    }),
    deleteLesson: build.mutation<void, string>({
      query: (id) => ({ url: `/lessons/${id}`, method: 'DELETE' }),
      invalidatesTags: ['LessonList'],
    }),
    /** Копія уроку в нову чернетку. Повтор із тим самим id нічого не дублює. */
    copyLesson: build.mutation<LessonOut, { sourceId: string; id: string; title?: string }>({
      query: ({ sourceId, id, title }) => ({ url: `/lessons/${sourceId}/copy`, method: 'POST', body: { id, title } }),
      invalidatesTags: ['LessonList'],
    }),

    createModule: build.mutation<
      ModuleOut,
      { lessonId: string; id: string; part: ModulePart; position: number; title: string; duration_min: number }
    >({
      query: ({ lessonId, ...body }) => ({ url: `/lessons/${lessonId}/modules`, method: 'POST', body }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    updateModule: build.mutation<
      ModuleOut,
      { lessonId: string; id: string; patch: Partial<Pick<ModuleOut, 'title' | 'duration_min'>> }
    >({
      query: ({ id, patch }) => ({ url: `/modules/${id}`, method: 'PATCH', body: patch }),
      onQueryStarted: ({ lessonId, id }, { dispatch, queryFulfilled }) =>
        applyResult(dispatch, lessonId, queryFulfilled, (lesson, data) => {
          const m = lesson.modules.find((x) => x.id === id)
          if (m) Object.assign(m, { title: data.title, duration_min: data.duration_min })
        }),
    }),
    deleteModule: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/modules/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    reorderModules: build.mutation<ModuleOut[], { lessonId: string; part: ModulePart; ids: string[] }>({
      query: ({ lessonId, part, ids }) => ({ url: `/lessons/${lessonId}/modules/order`, method: 'PUT', body: { part, ids } }),
      onQueryStarted: ({ lessonId, ids }, { dispatch, queryFulfilled }) =>
        optimistic(dispatch, lessonId, (lesson) => renumber(lesson.modules, ids), queryFulfilled),
    }),

    createCard: build.mutation<CardOut, CardCreateArgs>({
      query: ({ moduleId, id, position, kind, body, media_asset_id }) => ({
        url: `/modules/${moduleId}/cards`,
        method: 'POST',
        body: { id, position, kind, body, media_asset_id: media_asset_id ?? null },
      }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    /** Тіло картки повністю: { text } для тексту, { caption } для медіа. */
    updateCard: build.mutation<CardOut, { lessonId: string; id: string; body: Record<string, unknown> }>({
      query: ({ id, body }) => ({ url: `/cards/${id}`, method: 'PATCH', body: { body } }),
      onQueryStarted: ({ lessonId, id }, { dispatch, queryFulfilled }) =>
        applyResult(dispatch, lessonId, queryFulfilled, (lesson, data) => {
          const card = findCard(lesson, id)
          if (card) card.body = data.body
        }),
    }),
    deleteCard: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/cards/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    reorderCards: build.mutation<CardOut[], { lessonId: string; moduleId: string; ids: string[] }>({
      query: ({ moduleId, ids }) => ({ url: `/modules/${moduleId}/cards/order`, method: 'PUT', body: { ids } }),
      onQueryStarted: ({ lessonId, moduleId, ids }, { dispatch, queryFulfilled }) =>
        optimistic(
          dispatch,
          lessonId,
          (lesson) => {
            const m = lesson.modules.find((x) => x.id === moduleId)
            if (m) renumber(m.cards, ids)
          },
          queryFulfilled,
        ),
    }),

    createTest: build.mutation<
      TestOut,
      { lessonId: string; id: string; title: string; window_enabled: boolean; window_hours: WindowHours | null }
    >({
      query: ({ lessonId, ...body }) => ({ url: `/lessons/${lessonId}/tests`, method: 'POST', body }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    updateTest: build.mutation<
      TestOut,
      { lessonId: string; id: string; patch: Partial<Pick<TestOut, 'title' | 'window_enabled' | 'window_hours'>> }
    >({
      query: ({ id, patch }) => ({ url: `/tests/${id}`, method: 'PATCH', body: patch }),
      onQueryStarted: ({ lessonId, id }, { dispatch, queryFulfilled }) =>
        applyResult(dispatch, lessonId, queryFulfilled, (lesson, data) => {
          const t = lesson.tests.find((x) => x.id === id)
          if (t) Object.assign(t, { title: data.title, window_enabled: data.window_enabled, window_hours: data.window_hours })
        }),
    }),
    deleteTest: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/tests/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),

    createQuestion: build.mutation<
      QuestionOut,
      { lessonId: string; testId: string; id: string; position: number } & QuestionFields
    >({
      query: ({ lessonId: _lessonId, testId, ...body }) => ({ url: `/tests/${testId}/questions`, method: 'POST', body }),
      onQueryStarted: ({ lessonId, testId }, { dispatch, queryFulfilled }) =>
        applyResult(dispatch, lessonId, queryFulfilled, (lesson, data) => {
          const t = lesson.tests.find((x) => x.id === testId)
          if (t && !t.questions.some((q) => q.id === data.id)) t.questions.push(data)
        }),
      invalidatesTags: ['LessonList'],
    }),
    /** Питання повністю (сервер перевіряє після злиття, тож шлемо всі поля разом). */
    updateQuestion: build.mutation<QuestionOut, { lessonId: string; id: string } & QuestionFields>({
      query: ({ lessonId: _lessonId, id, ...body }) => ({ url: `/questions/${id}`, method: 'PATCH', body }),
      onQueryStarted: ({ lessonId, id }, { dispatch, queryFulfilled }) =>
        applyResult(dispatch, lessonId, queryFulfilled, (lesson, data) => {
          const q = findQuestion(lesson, id)
          if (q) Object.assign(q, data)
        }),
    }),
    deleteQuestion: build.mutation<void, { lessonId: string; id: string }>({
      query: ({ id }) => ({ url: `/questions/${id}`, method: 'DELETE' }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    reorderQuestions: build.mutation<QuestionOut[], { lessonId: string; testId: string; ids: string[] }>({
      query: ({ testId, ids }) => ({ url: `/tests/${testId}/questions/order`, method: 'PUT', body: { ids } }),
      onQueryStarted: ({ lessonId, testId, ids }, { dispatch, queryFulfilled }) =>
        optimistic(
          dispatch,
          lessonId,
          (lesson) => {
            const t = lesson.tests.find((x) => x.id === testId)
            if (t) renumber(t.questions, ids)
          },
          queryFulfilled,
        ),
    }),

    /** Стан медіа: для відео, яке стискає сервер, опитуємо до ready/failed. */
    media: build.query<MediaOut, string>({
      query: (id) => `/media/${id}`,
    }),
    /** Прив'язати VTT-субтитри до відео. */
    attachSubtitles: build.mutation<MediaOut, { lessonId: string; videoId: string; subtitlesId: string | null }>({
      query: ({ videoId, subtitlesId }) => ({ url: `/media/${videoId}`, method: 'PATCH', body: { subtitles_id: subtitlesId } }),
      invalidatesTags: (_result, _error, { lessonId }) => lessonTag(lessonId),
    }),
    /** Ще будується: файл з Wikimedia Commons за посиланням (лише вільні ліцензії). */
    importCommons: build.mutation<MediaOut, { id: string; url: string }>({
      query: (body) => ({ url: '/media/import/commons', method: 'POST', body }),
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

export const { useLessonQuery } = lessonQueryApi
export { lessonQueryApi }

export const {
  useCreateLessonMutation,
  useUpdateLessonMutation,
  useDeleteLessonMutation,
  useCopyLessonMutation,
  useCreateModuleMutation,
  useUpdateModuleMutation,
  useDeleteModuleMutation,
  useReorderModulesMutation,
  useCreateCardMutation,
  useUpdateCardMutation,
  useDeleteCardMutation,
  useReorderCardsMutation,
  useCreateTestMutation,
  useUpdateTestMutation,
  useDeleteTestMutation,
  useCreateQuestionMutation,
  useUpdateQuestionMutation,
  useDeleteQuestionMutation,
  useReorderQuestionsMutation,
  useMediaQuery,
  useAttachSubtitlesMutation,
  useImportCommonsMutation,
  usePublishLessonMutation,
  useUnpublishLessonMutation,
  useAssignLessonMutation,
  useUnassignLessonMutation,
} = lessonEditorApi

/** Наступна вільна позиція в групі: сервер не перенумеровує, зайнята дає 409 POSITION_TAKEN. */
export function nextPosition(items: { position: number }[]): number {
  return items.reduce((max, item) => Math.max(max, item.position + 1), 1)
}

/** Код помилки бекенду (або null). */
export function errorCode(error: unknown): string | null {
  return (error as ApiError)?.data?.error?.code ?? null
}

/** Помилка мережі (або сервер недоступний): дію варто повторити пізніше. */
export function isNetworkError(error: unknown): boolean {
  const status = (error as ApiError)?.status
  return status === 'FETCH_ERROR' || status === 'TIMEOUT_ERROR' || (typeof status === 'number' && status >= 500)
}

/** Ендпоінта ще немає на сервері (частина контракту, що будується). */
export function isNotAvailable(error: unknown): boolean {
  const status = (error as ApiError)?.status
  return status === 404 || status === 405
}

/** Зрозуміле вчителю повідомлення з помилки бекенду. */
export function errorMessage(error: unknown): string {
  const e = error as ApiError
  switch (errorCode(error)) {
    case 'LESSON_NOT_PUBLISHABLE':
      return 'Урок поки не можна опублікувати. Перегляньте список нижче.'
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
    case 'ORDER_MISMATCH':
      return 'Урок щойно змінився. Оновіть сторінку й спробуйте ще раз.'
    case 'ID_CONFLICT':
      return 'Конфлікт даних. Оновіть сторінку й спробуйте ще раз.'
    case 'FORBIDDEN':
      return 'Змінювати урок може лише його автор.'
    case 'LICENSE_NOT_ALLOWED':
      return 'Ліцензія цього файла не дозволяє використати його в уроці. Оберіть інший файл.'
    case 'MEDIA_TOO_LARGE':
      return 'Файл завеликий.'
    case 'UNSUPPORTED_MEDIA_TYPE':
      return 'Такий формат файла не підтримується.'
    case 'INVALID_MEDIA':
    case 'INVALID_IMAGE':
      return 'Файл пошкоджений або не того формату.'
    case 'IMAGE_TOO_LARGE':
      return 'Зображення завелике за розміром у пікселях.'
  }
  if (e?.status === 422) return 'Перевірте поля: щось заповнено неправильно.'
  if (isNetworkError(error)) return 'Немає звʼязку з сервером. Перевірте мережу й спробуйте ще раз.'
  return e?.data?.error?.message ?? 'Не вдалося зберегти. Спробуйте ще раз.'
}

/** Перевірки публікації, які не пройшли (details помилки LESSON_NOT_PUBLISHABLE). */
export function publishChecks(error: unknown): LessonCheck[] {
  if (errorCode(error) !== 'LESSON_NOT_PUBLISHABLE') return []
  const details = (error as ApiError).data?.error?.details
  return Array.isArray(details) ? details.filter((d): d is LessonCheck => typeof (d as LessonCheck)?.check === 'string') : []
}
