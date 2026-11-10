import { useState } from 'react'
import { skipToken } from '@reduxjs/toolkit/query/react'
import {
  useClassesQuery,
  useClassRollCallQuery,
  useCloseRollCallMutation,
  useStartRollCallMutation,
} from './teacherApi'

/** Як часто вчитель оновлює екран переклички (docs/sync-protocol.md: опитування кожні 10 с). */
const POLL_MS = 10_000

/**
 * Перекличка першого класу вчителя. Кілька класів: поки береться перший, вибір класу — окремий крок.
 * Дані оновлюються опитуванням, поки вкладка у фокусі (енергоменеджер: без фонових запитів).
 * Без мережі лишаються останні отримані дані, а isOffline = true.
 */
export function useTeacherRollCall() {
  const classes = useClassesQuery()
  const teacherClass = classes.data?.[0]
  const rollCall = useClassRollCallQuery(teacherClass?.id ?? skipToken, {
    pollingInterval: POLL_MS,
    skipPollingIfUnfocused: true,
  })
  const [startMutation, startState] = useStartRollCallMutation()
  const [closeMutation, closeState] = useCloseRollCallMutation()
  const [actionError, setActionError] = useState<string | null>(null)

  const session = rollCall.data?.session ?? null
  const open = session && !session.closed_at ? session : null

  const run = async (action: () => Promise<unknown>) => {
    setActionError(null)
    try {
      await action()
      await rollCall.refetch()
    } catch {
      setActionError('Не вдалося виконати дію. Перевірте звʼязок і спробуйте ще раз.')
    }
  }

  const start = (isDrill: boolean) => {
    if (!teacherClass) return Promise.resolve()
    return run(() => startMutation({ classId: teacherClass.id, isDrill }).unwrap())
  }

  const close = () => {
    if (!teacherClass || !open) return Promise.resolve()
    return run(() => closeMutation({ classId: teacherClass.id, sessionId: open.id }).unwrap())
  }

  return {
    teacherClass,
    session: open,
    isLoading: classes.isLoading || rollCall.isLoading,
    isOffline: classes.isError || rollCall.isError,
    busy: startState.isLoading || closeState.isLoading,
    actionError,
    start,
    close,
    /** Одразу оновити перекличку (наприклад, після ручної тривоги, що її відкриває) */
    refresh: () => void rollCall.refetch(),
  }
}
