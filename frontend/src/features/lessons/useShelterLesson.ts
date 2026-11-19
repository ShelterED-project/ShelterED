import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { useLiveQuery } from 'dexie-react-hooks'
import { useAppSelector } from '@/app/hooks'
import { pickCurrentLesson, useTodayPack } from '@/features/packs/usePacks'
import type { TodayLesson } from '@/features/packs/usePacks'
import { db } from '@/shared/db/db'
import type { LessonProgressRecord } from '@/shared/db/types'
import { buildSteps } from './lessonSteps'
import type { LessonStep } from './lessonSteps'

export interface ShelterLesson {
  /** false, поки пакет за сьогодні не збережено на пристрої */
  hasPack: boolean
  /** Уроки дня: для вибору іншого уроку */
  lessons: TodayLesson[]
  /** Обраний урок: з ?lesson=, інакше поточний або найближчий */
  lesson: TodayLesson | null
  steps: LessonStep[]
  /** Перший непройдений крок; null, коли весь урок пройдено */
  currentStep: LessonStep | null
  /** Частка пройдених кроків, 0..1 */
  progress: number
  /** Локальний прогрес обраного уроку: зокрема результати тестів від сервера */
  records: LessonProgressRecord[]
  select: (lessonId: string) => void
}

/**
 * Урок для екрана укриття. Усе з IndexedDB (пакет і локальний прогрес), без мережі.
 * Обраний урок живе в адресі (?lesson=), тож переживає перезавантаження й ділиться посиланням.
 */
export function useShelterLesson(): ShelterLesson {
  const { lessons } = useTodayPack()
  const [params, setParams] = useSearchParams()

  const requestedId = params.get('lesson')
  const lesson = useMemo(
    () => lessons?.find((l) => l.lesson.id === requestedId) ?? pickCurrentLesson(lessons) ?? lessons?.[0] ?? null,
    [lessons, requestedId],
  )

  const lessonId = lesson?.lesson.id
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  // Лише свій прогрес: на спільному пристрої інші учні могли проходити той самий урок.
  const records = useLiveQuery(
    () => (lessonId && userId ? db.userProgress.where('[user_id+lesson_id]').equals([userId, lessonId]).toArray() : []),
    [lessonId, userId],
  )

  const steps = useMemo(() => (lesson ? buildSteps(lesson.lesson, records ?? []) : []), [lesson, records])
  const currentStep = steps.find((step) => !step.done) ?? null
  const doneCount = steps.filter((step) => step.done).length

  return {
    hasPack: lessons !== null,
    lessons: lessons ?? [],
    lesson,
    steps,
    currentStep,
    progress: steps.length === 0 ? 0 : doneCount / steps.length,
    records: records ?? [],
    select: (id) => setParams({ lesson: id }, { replace: true }),
  }
}
