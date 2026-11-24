import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { errorMessage, useCopyLessonMutation } from '@/features/teacher/lessonEditorApi'
import { generateId } from '@/shared/lib/uuid'
import { copyTitle } from './content'

/**
 * Копія уроку в нову чернетку «<назва> (копія)» і перехід до неї. Id копії для кожного уроку
 * фіксується до успіху: повтор після обриву мережі не створить другу копію.
 */
export function useCopyLesson() {
  const [copy] = useCopyLessonMutation()
  const navigate = useNavigate()
  const ids = useRef(new Map<string, string>())
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<{ id: string; message: string } | null>(null)

  const run = async (source: { id: string; title: string }) => {
    let id = ids.current.get(source.id)
    if (!id) {
      id = generateId()
      ids.current.set(source.id, id)
    }
    setBusyId(source.id)
    setError(null)
    try {
      await copy({ sourceId: source.id, id, title: copyTitle(source.title) }).unwrap()
      ids.current.delete(source.id)
      navigate(`/teacher/lessons/${id}`)
    } catch (err) {
      setError({ id: source.id, message: errorMessage(err) })
    } finally {
      setBusyId(null)
    }
  }

  return { run, busyId, error }
}
