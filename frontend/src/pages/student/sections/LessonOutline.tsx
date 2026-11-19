import iconQueue from '@/assets/shelter/queue.svg'
import iconCheck from '@/assets/student/lesson-check.svg'
import type { LessonStep } from '@/features/lessons/lessonSteps'
import { useShelterLesson } from '@/features/lessons/useShelterLesson'
import { lessonPage as texts } from '../content'

type State = 'done' | 'current' | 'todo'

function Marker({ state }: { state: State }) {
  if (state === 'done') {
    return (
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent">
        <img src={iconCheck} alt="" width={14} height={14} />
      </span>
    )
  }
  if (state === 'current') {
    return (
      <span className="relative size-7 shrink-0">
        <span className="absolute -inset-[3px] flex items-center justify-center rounded-full border-[3px] border-parchment bg-oil">
          <span className="size-7 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />
        </span>
      </span>
    )
  }
  return <span className="size-7 shrink-0 rounded-full border-2 border-line-strong" />
}

type Item = { step: LessonStep; label: string; note: string }

function Group({ title, items, currentId, divided }: { title: string; items: Item[]; currentId?: string; divided: boolean }) {
  return (
    <div className={`flex flex-col gap-1 ${divided ? 'border-t border-line-soft pt-3' : ''}`}>
      <h3 className="text-xs leading-4 font-semibold tracking-[0.96px] text-accent uppercase">{title}</h3>
      <ol className="flex flex-col">
        {items.map(({ step, label, note }) => {
          const state: State = step.done ? 'done' : step.id === currentId ? 'current' : 'todo'
          return (
            <li key={step.id} aria-current={state === 'current' ? 'step' : undefined} className="flex items-center gap-3 py-2.5">
              <Marker state={state} />
              <div className="flex min-w-0 flex-col">
                <span
                  className={`text-sm leading-5 ${state === 'current' ? 'font-semibold text-parchment' : state === 'done' ? 'text-parchment' : 'text-dim'}`}
                >
                  {label}
                </span>
                <span className="text-[11px] leading-[16.5px] text-dim">{note}</span>
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/** План уроку: модулі укриттєвої й основної частини та тести, з позначкою пройденого. */
export function LessonOutline() {
  const { lesson, steps, currentStep } = useShelterLesson()
  if (!lesson || steps.length === 0) return null

  const shelter: Item[] = []
  const main: Item[] = []
  let moduleNumber = 0
  for (const step of steps) {
    if (step.kind === 'module') {
      moduleNumber += 1
      const item = { step, label: texts.module(moduleNumber, step.title), note: texts.moduleMinutes(step.module.duration_min) }
      ;(step.module.part === 'shelter' ? shelter : main).push(item)
    } else {
      const { test } = step
      main.push({
        step,
        label: texts.test(test.questions.length),
        note: test.window_enabled && test.window_hours ? texts.testWindow(test.window_hours) : texts.testPractice,
      })
    }
  }

  return (
    <section aria-labelledby="outline-title" className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-6">
      <h2 id="outline-title" className="font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">
        {lesson.lesson.title}
      </h2>
      <div className="flex flex-col gap-3">
        {shelter.length > 0 && <Group title={texts.outline.shelter} items={shelter} currentId={currentStep?.id} divided={false} />}
        {main.length > 0 && (
          <Group title={texts.outline.main} items={main} currentId={currentStep?.id} divided={shelter.length > 0} />
        )}
      </div>
    </section>
  )
}

/** Скільки подій чекає на відправку: дані лишаються на пристрої, доки сервер не підтвердить. */
export function LessonQueue({ pending }: { pending: number }) {
  return (
    <section className="flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5">
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2">
          <img src={iconQueue} alt="" width={20} height={20} />
        </span>
        <div className="flex min-w-0 flex-col">
          <p role="status" className="text-sm leading-5 font-semibold text-parchment">
            {texts.queue(pending)}
          </p>
          <p className="text-xs leading-4 text-dim">{pending === 0 ? texts.queueSent : texts.queueWaiting}</p>
        </div>
      </div>
      <p className="text-xs leading-4 text-dim">{texts.queueNote}</p>
    </section>
  )
}
