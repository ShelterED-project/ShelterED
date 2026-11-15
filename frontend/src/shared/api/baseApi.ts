import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { BaseQueryFn, FetchArgs, FetchBaseQueryError } from '@reduxjs/toolkit/query/react'
import type { AuthState } from '@/features/auth/authSlice'
import { OAUTH_CLIENT_ID } from '@/features/auth/pkce'
import { clearSession, saveSession, sessionFromTokens } from '@/features/auth/session'
import type { TokenResponse } from '@/features/auth/types'

const baseUrl = import.meta.env.VITE_API_BASE_URL

/** Оновлюємо токен заздалегідь, щоб запит не вперся в 401. */
const REFRESH_MARGIN_MS = 10_000

const rawBaseQuery = fetchBaseQuery({
  baseUrl,
  prepareHeaders: (headers, { getState }) => {
    const session = (getState() as { auth: AuthState }).auth.session
    // Явний Authorization (напр. fetchMe під час входу) не перезаписуємо токеном старої сесії.
    if (session && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${session.accessToken}`)
    return headers
  },
})

type RefreshResult = 'ok' | 'rejected' | 'offline'

/**
 * Refresh-токен ротується: повторне використання вже обробленого відкликає весь вхід.
 * Тому паралельні запити ділять один спільний refresh (single-flight).
 */
let refreshing: Promise<RefreshResult> | null = null

function refreshSession(
  api: Parameters<BaseQueryFn>[1],
  refreshToken: string,
  persist: boolean,
  user: NonNullable<AuthState['session']>['user'],
): Promise<RefreshResult> {
  refreshing ??= (async (): Promise<RefreshResult> => {
    try {
      const response = await fetch(`${baseUrl}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: OAUTH_CLIENT_ID,
        }),
      })
      if (!response.ok) {
        // Бекенд явно відхилив токен: сесії кінець. 5xx — не підстава розлогінювати.
        return response.status >= 500 ? 'offline' : 'rejected'
      }
      const tokens = (await response.json()) as TokenResponse
      await saveSession(api.dispatch, sessionFromTokens(tokens, user), persist)
      return 'ok'
    } catch {
      // Немає мережі: сесію не чіпаємо, інтерфейс працює з локальними даними.
      return 'offline'
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

const baseQueryWithReauth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (
  args,
  api,
  extraOptions,
) => {
  const auth = (api.getState() as { auth: AuthState }).auth
  const session = auth.session

  if (session && session.expiresAt - Date.now() < REFRESH_MARGIN_MS) {
    const result = await refreshSession(api, session.refreshToken, auth.persisted, session.user)
    if (result === 'rejected') await clearSession(api.dispatch)
  }

  let result = await rawBaseQuery(args, api, extraOptions)

  // 401 з токеном у запиті: токен міг бути відкликаний/прострочений раніше за expiresAt.
  if (result.error?.status === 401 && session) {
    const current = (api.getState() as { auth: AuthState }).auth
    if (current.session) {
      const refreshed = await refreshSession(
        api,
        current.session.refreshToken,
        current.persisted,
        current.session.user,
      )
      if (refreshed === 'ok') result = await rawBaseQuery(args, api, extraOptions)
      else if (refreshed === 'rejected') await clearSession(api.dispatch)
    }
  }
  return result
}

export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: baseQueryWithReauth,
  // Теги кешу: після змін уроку у вчителя оновлюються список уроків, відкритий урок і розклад.
  tagTypes: ['Lesson', 'LessonList', 'Schedule'],
  endpoints: () => ({}),
})
