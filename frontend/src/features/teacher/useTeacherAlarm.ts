import { useState } from 'react'
import { useEndAlertMutation, useStartManualAlertMutation } from '@/features/alerts/alertsApi'
import { useActiveAlert } from '@/features/alerts/useActiveAlert'
import { useTeacherRollCall } from './useTeacherRollCall'

/** Що саме зараз виконується: для лоадера на потрібній кнопці. */
export type AlarmAction = 'drill' | 'real' | 'end'

/**
 * Ручна тривога вчителя для свого класу (перший клас вчителя, як і в перекличці).
 * Бекенд сам відкриває перекличку класу й ставить push; відбій закриває перекличку.
 */
export function useTeacherAlarm() {
  const { teacherClass, refresh: refreshRollCall } = useTeacherRollCall()
  const { alert, refresh: refreshAlert } = useActiveAlert()
  const [startMutation] = useStartManualAlertMutation()
  const [endMutation] = useEndAlertMutation()
  const [pending, setPending] = useState<AlarmAction | null>(null)
  const [error, setError] = useState<string | null>(null)

  // pending тримається, доки не прийде свіжий стан тривоги й переклички:
  // інакше між відповіддю POST і оновленням кнопка ще показує старий стан і здається, що нічого не сталося.
  const run = async (kind: AlarmAction, action: () => Promise<unknown>): Promise<boolean> => {
    setError(null)
    setPending(kind)
    try {
      await action()
      await Promise.allSettled([refreshAlert(), refreshRollCall()])
      return true
    } catch {
      setError('Не вдалося виконати дію. Перевірте звʼязок і спробуйте ще раз.')
      return false
    } finally {
      setPending(null)
    }
  }

  const start = (isDrill: boolean) => {
    if (!teacherClass) return Promise.resolve(false)
    return run(isDrill ? 'drill' : 'real', () => startMutation({ classId: teacherClass.id, isDrill }).unwrap())
  }

  // Тривогу з API закінчує лише API (409), тож відбій доступний тільки для ручної.
  const manualAlert = alert?.source === 'manual' ? alert : null
  const end = () => {
    if (!manualAlert) return Promise.resolve(false)
    return run('end', () => endMutation(manualAlert.id).unwrap())
  }

  return {
    canStart: Boolean(teacherClass),
    manualAlert,
    busy: pending !== null,
    pending,
    error,
    start,
    end,
  }
}
