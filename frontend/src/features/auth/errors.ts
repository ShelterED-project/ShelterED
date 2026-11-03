import type { SerializedError } from '@reduxjs/toolkit'
import type { FetchBaseQueryError } from '@reduxjs/toolkit/query'
import type { ApiErrorBody } from './types'

type QueryError = FetchBaseQueryError | SerializedError | undefined

const messages: Record<string, string> = {
  INVALID_CREDENTIALS: 'Невірна пошта, пароль або PIN',
  INVALID_CLIENT: 'Невідомий застосунок. Зверніться до адміністрації',
  INVALID_GRANT: 'Сесія застаріла. Увійдіть ще раз',
  INVALID_REQUEST: 'Некоректний запит',
  INVALID_JOIN_CODE: 'Невірний код класу',
  INVALID_LINK_CODE: 'Невірний або прострочений код',
  EMAIL_TAKEN: 'Користувач з такою поштою вже існує',
  VALIDATION_ERROR: 'Перевірте введені дані',
  FORBIDDEN: 'Недостатньо прав',
  UNAUTHORIZED: 'Потрібно увійти',
  NOT_FOUND: 'Не знайдено',
  INTERNAL_ERROR: 'Помилка сервера. Спробуйте пізніше',
}

export const OFFLINE_MESSAGE = 'Немає зʼєднання з сервером. Спробуйте, коли зʼявиться мережа'

function isApiErrorBody(data: unknown): data is ApiErrorBody {
  return (
    typeof data === 'object' &&
    data !== null &&
    'error' in data &&
    typeof (data as ApiErrorBody).error?.code === 'string'
  )
}

/** Код помилки бекенда (`error.code`), якщо відповідь у його форматі. */
export function getErrorCode(error: QueryError): string | undefined {
  if (error && 'data' in error && isApiErrorBody(error.data)) return error.data.error.code
  return undefined
}

/** Українське повідомлення для помилки запиту RTK Query. */
export function getErrorMessage(error: QueryError): string {
  if (!error) return ''
  if ('status' in error && (error.status === 'FETCH_ERROR' || error.status === 'TIMEOUT_ERROR')) {
    return OFFLINE_MESSAGE
  }
  const code = getErrorCode(error)
  if (code && messages[code]) return messages[code]
  return 'Щось пішло не так. Спробуйте ще раз'
}
