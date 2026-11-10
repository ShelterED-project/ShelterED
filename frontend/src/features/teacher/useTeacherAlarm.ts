import { useState } from 'react'
import { useEndAlertMutation, useStartManualAlertMutation } from '@/features/alerts/alertsApi'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import { useTeacherRollCall } from './useTeacherRollCall'

/**
 * Ручна тривога вчителя для свого класу (перший клас вчителя, як і в перекличці).
 * Бекенд сам відкриває перекличку класу й ставить push; відбій закриває перекличку.
 */
export function useTeacherAlarm() {
  const { teacherClass, refresh: refreshRollCall } = useTeacherRollCall()
  const { alert, refresh: refreshAlert } = useActiveAlert()
  const [startMutation, startState] = useStartManualAlertMutation()
  const [endMutation, endState] = useEndAlertMutation()
  const [error, setError] = useState<string | null>(null)

  const run = async (action: () => Promise<unknown>) => {
    setError(null)
    try {
      await action()
      refreshAlert()
      refreshRollCall()
    } catch {
      setError('Не вдалося виконати дію. Перевірте звʼязок і спробуйте ще раз.')
    }
  }

  const start = (isDrill: boolean) => {
    if (!teacherClass) return Promise.resolve()
    return run(() => startMutation({ classId: teacherClass.id, isDrill }).unwrap())
  }

  // Тривогу з API закінчує лише API (409), тож відбій доступний тільки для ручної.
  const manualAlert = alert?.source === 'manual' ? alert : null
  const end = () => {
    if (!manualAlert) return Promise.resolve()
    return run(() => endMutation(manualAlert.id).unwrap())
  }

  return {
    canStart: Boolean(teacherClass),
    manualAlert,
    busy: startState.isLoading || endState.isLoading,
    error,
    start,
    end,
  }
}
