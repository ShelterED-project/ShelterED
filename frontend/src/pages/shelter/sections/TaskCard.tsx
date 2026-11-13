import type { ReactNode } from 'react'
import iconCheck from '@/assets/shelter/check-dim.svg'
import { useAppSelector } from '@/app/hooks'
import { useShelterLesson } from '@/features/lessons/useShelterLesson'
import { task } from '../content'
import ModuleTask from './ModuleTask'
import TestResults from './TestResults'
import TestTask from './TestTask'

/** Рамка завдання: підпис зверху, заголовок і тіло. Спільна для модуля, тесту й порожніх станів. */
export function TaskFrame({ meta, title, children }: { meta?: string; title: string; children?: ReactNode }) {
  return (
    <section
      id="task"
      aria-labelledby="task-title"
      className="flex flex-col gap-[11px] rounded-3xl border border-line bg-surface p-5 xl:p-7"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs leading-4 text-dim">{meta}</p>
        <p className="flex items-center gap-1.5 text-xs leading-4 text-dim">
          <img src={iconCheck} alt="" width={16} height={16} className="shrink-0" />
          {task.saved}
        </p>
      </div>
      <h2
        id="task-title"
        className="font-heading text-[22px] leading-[27.5px] tracking-[-0.22px] text-parchment xl:text-[26px] xl:leading-[32.5px] xl:tracking-[-0.26px]"
      >
        {title}
      </h2>
      {children}
    </section>
  )
}

export default function TaskCard() {
  const { lesson, currentStep, steps, records } = useShelterLesson()
  const userId = useAppSelector((s) => s.auth.session?.user.id)

  if (!lesson || !userId) return <TaskFrame title={task.empty} />
  if (!currentStep) {
    return (
      <TaskFrame title={task.allDone}>
        <TestResults steps={steps} records={records} />
      </TaskFrame>
    )
  }

  // key: при переході до наступного кроку стан завдання починається з нуля.
  return currentStep.kind === 'module' ? (
    <ModuleTask key={currentStep.id} userId={userId} lessonId={lesson.lesson.id} module={currentStep.module} />
  ) : (
    <TestTask key={currentStep.id} userId={userId} lessonId={lesson.lesson.id} test={currentStep.test} />
  )
}
