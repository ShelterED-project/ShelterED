import type { PackLesson, PackModule, PackTest } from '@/shared/db/packTypes'
import type { LessonProgressRecord } from '@/shared/db/types'

export type LessonStep =
  | { id: string; kind: 'module'; title: string; module: PackModule; done: boolean }
  | { id: string; kind: 'test'; title: string; test: PackTest; done: boolean }

/** Укриттєва частина йде першою: саме її вчитель підготував для уроку в укритті. */
const PART_ORDER: Record<string, number> = { shelter: 0, main: 1 }

function partRank(part: string): number {
  return PART_ORDER[part] ?? 2
}

/** Кроки уроку: модулі (спершу укриттєві), потім тести. done береться з локального прогресу. */
export function buildSteps(lesson: PackLesson, progress: LessonProgressRecord[]): LessonStep[] {
  const doneIds = new Set(progress.map((record) => record.id))
  const modules = [...lesson.modules].sort(
    (a, b) => partRank(a.part) - partRank(b.part) || a.position - b.position,
  )
  return [
    ...modules.map((module): LessonStep => ({
      id: module.id,
      kind: 'module',
      title: module.title,
      module,
      done: doneIds.has(module.id),
    })),
    ...lesson.tests.map((test): LessonStep => ({
      id: test.id,
      kind: 'test',
      title: test.title,
      test,
      done: doneIds.has(test.id),
    })),
  ]
}
