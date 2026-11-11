import { useState } from 'react'
import { errorMessage } from '@/features/teacher/lessonEditorApi'

/** Одна дія редактора: стан «виконується» для лоадера й зрозуміла помилка. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (action: () => Promise<unknown>): Promise<boolean> => {
    setBusy(true)
    setError(null)
    try {
      await action()
      return true
    } catch (err) {
      setError(errorMessage(err))
      return false
    } finally {
      setBusy(false)
    }
  }

  return { busy, error, run }
}
