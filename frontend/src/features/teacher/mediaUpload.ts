import { useCallback } from 'react'
import { useStore } from 'react-redux'
import type { AppDispatch, RootState } from '@/app/store'
import { lessonQueryApi } from './lessonEditorApi'
import type { ApiError, MediaOut } from './lessonEditorApi'

const baseUrl = import.meta.env.VITE_API_BASE_URL

/** `video_source` — оригінал відео, який стискає сервер (ще будується). */
export type UploadKind = 'video' | 'image' | 'subtitles' | 'video_source'

export interface UploadArgs {
  /** Id медіа створює клієнт: повтор того самого файла з тим самим id нічого не дублює */
  id: string
  kind: UploadKind
  file: Blob
  /** Тип файла для Content-Type (за замовчуванням file.type) */
  mime?: string
  /** Урок, у якому працюємо: через нього оновлюємо токен, якщо він сплив */
  lessonId: string
  /** Частка відправленого 0..1 */
  onProgress?: (share: number) => void
  signal?: AbortSignal
}

/** Помилка у формі RTK Query (ApiError), щоб errorMessage() розумів її так само. */
function apiError(status: number | string, body: unknown): ApiError {
  return { status, data: (body ?? undefined) as ApiError['data'] }
}

function put(args: UploadArgs, token: string | null): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    // Сирий вміст файла (не multipart), тип — у Content-Type.
    xhr.open('PUT', `${baseUrl}/media/${args.id}?kind=${args.kind}`)
    xhr.setRequestHeader('Content-Type', args.mime ?? args.file.type)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) args.onProgress?.(e.loaded / e.total)
    }
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }
      resolve({ status: xhr.status, body })
    }
    xhr.onerror = () => reject(apiError('FETCH_ERROR', null))
    xhr.onabort = () => reject(apiError('ABORTED', null))
    args.signal?.addEventListener('abort', () => xhr.abort())
    xhr.send(args.file)
  })
}

/**
 * Завантаження медіа з прогресом (XHR: fetch не повідомляє прогрес відправки). Токен той самий,
 * що в RTK Query; якщо він сплив, оновлюємо його звичайним запитом уроку (baseQuery сам робить
 * refresh) і пробуємо ще раз.
 */
export function useMediaUploader() {
  const store = useStore<RootState>()

  return useCallback(
    async (args: UploadArgs): Promise<MediaOut> => {
      const dispatch = store.dispatch as AppDispatch
      const refresh = async () => {
        await dispatch(lessonQueryApi.endpoints.lesson.initiate(args.lessonId, { forceRefetch: true, subscribe: false }))
      }
      const session = store.getState().auth.session
      if (session && session.expiresAt - Date.now() < 60_000) await refresh()

      let result = await put(args, store.getState().auth.session?.accessToken ?? null)
      if (result.status === 401) {
        await refresh()
        result = await put(args, store.getState().auth.session?.accessToken ?? null)
      }
      if (result.status >= 200 && result.status < 300) return result.body as MediaOut
      throw apiError(result.status, result.body)
    },
    [store],
  )
}
