import { useEffect, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { useAppSelector } from '@/app/hooks'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import { db } from '@/shared/db/db'
import { rejectionKey } from '@/shared/db/outbox'
import { cacheSessionId, getCachedSessionId, markStatus } from './rollCall'
import { useStudentRollCallQuery } from './rollCallApi'
import type { RollCallStatus } from './types'

/** Скільки чекати свіжу сесію з сервера перед відміткою, далі — остання відома. */
const FRESH_TIMEOUT_MS = 3_000

const NO_SESSION = 'Зараз немає активної переклички. Спробуйте, коли вчитель її запустить.'

/**
 * Що сталося з останньою відміткою: ще в черзі на пристрої, сервер прийняв, або відхилив
 * (наприклад, перекличку вже закрито) — тоді причина з відповіді сервера.
 */
export type RollCallDelivery =
  | { state: 'pending' }
  | { state: 'delivered' }
  | { state: 'rejected'; reason: string }

/**
 * Відмітка в перекличці: пише подію в outbox і стежить, чим вона закінчилась.
 * session_id беремо з сервера щоразу перед відміткою: перекличка могла відкритися вже після того,
 * як учень відкрив застосунок (разом із тривогою). Без мережі — остання відома сесія.
 */
export function useRollCall() {
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  // Свіжа сесія при кожному відкритті картки (режим укриття, «Маршрут»), а не кеш із моменту входу.
  const { data, isSuccess, refetch } = useStudentRollCallQuery(userId ?? '', {
    skip: !userId,
    refetchOnMountOrArgChange: true,
  })
  // Тривога відкриває перекличку на сервері: щойно вона зʼявилась, підтягуємо нову сесію.
  // Окремого опитування переклички немає — тривоги й так опитуються (енергоменеджер).
  const { alert } = useActiveAlert()
  const alertId = alert?.id ?? null
  const [last, setLast] = useState<{ status: RollCallStatus; eventId: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Сервер відповів: актуальна сесія (або її відсутність) замінює кеш.
  useEffect(() => {
    if (isSuccess) void cacheSessionId(data.session_id)
  }, [isSuccess, data])

  // Подія в черзі — ще не відправлено; зникла без відмови — сервер прийняв; є відмова — не враховано.
  const delivery = useLiveQuery(async (): Promise<RollCallDelivery | null> => {
    if (!last) return null
    const rejected = await db.meta.get(rejectionKey(last.eventId))
    if (rejected) return { state: 'rejected', reason: String(rejected.value) }
    return (await db.events.get(last.eventId)) ? { state: 'pending' } : { state: 'delivered' }
  }, [last])

  useEffect(() => {
    if (alertId && userId) void refetch()
  }, [alertId, userId, refetch])

  // Відхилено: сесія на сервері могла закритися, тож оновлюємо її (і кеш для офлайну).
  const rejected = delivery?.state === 'rejected'
  useEffect(() => {
    if (rejected && userId) void refetch()
  }, [rejected, userId, refetch])

  const mark = async (status: RollCallStatus) => {
    if (!userId) return
    // Спершу питаємо сервер: перекличку могли відкрити щойно. Не відповів (офлайн) —
    // остання відома сесія: з цієї відповіді або збережена на пристрої.
    // На поганому звʼязку не тримаємо дитину: чекаємо відповіді не довше FRESH_TIMEOUT_MS.
    const fresh = await Promise.race([
      refetch(),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), FRESH_TIMEOUT_MS)),
    ])
    const sessionId = fresh?.isSuccess
      ? fresh.data.session_id
      : isSuccess
        ? data.session_id
        : await getCachedSessionId()
    if (fresh?.isSuccess) void cacheSessionId(fresh.data.session_id)
    if (!sessionId) {
      setError(NO_SESSION)
      return
    }
    const event = await markStatus(userId, sessionId, status)
    setError(null)
    setLast({ status, eventId: event.client_event_id })
  }

  return { lastStatus: last?.status ?? null, delivery: delivery ?? null, error, mark }
}
