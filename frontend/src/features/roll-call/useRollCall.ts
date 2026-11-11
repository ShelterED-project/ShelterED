import { useEffect, useState } from 'react'
import { useAppSelector } from '@/app/hooks'
import { cacheSessionId, getCachedSessionId, markStatus } from './rollCall'
import { useStudentRollCallQuery } from './rollCallApi'
import type { RollCallStatus } from './types'

const NO_SESSION = 'Зараз немає активної переклички. Спробуйте, коли вчитель її запустить.'

/**
 * Відмітка в перекличці: пише подію в outbox і памʼятає останній вибраний статус.
 * session_id беремо з сервера; без мережі використовуємо останню відому сесію.
 */
export function useRollCall() {
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  const { data, isSuccess } = useStudentRollCallQuery(userId ?? '', { skip: !userId })
  const [lastStatus, setLastStatus] = useState<RollCallStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Сервер відповів: актуальна сесія (або її відсутність) замінює кеш.
  useEffect(() => {
    if (isSuccess) void cacheSessionId(data.session_id)
  }, [isSuccess, data])

  const mark = async (status: RollCallStatus) => {
    if (!userId) return
    // Свіжа відповідь сервера має пріоритет. Кеш лише тоді, коли відповіді немає (офлайн).
    const sessionId = isSuccess ? data.session_id : await getCachedSessionId()
    if (!sessionId) {
      setError(NO_SESSION)
      return
    }
    await markStatus(userId, sessionId, status)
    setError(null)
    setLastStatus(status)
  }

  return { lastStatus, error, mark }
}
