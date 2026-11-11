import { useShelterLesson } from '@/features/lessons/useShelterLesson'
import { pluralUk } from '@/shared/lib/plural'
import { next } from '../content'

export default function NextOffline() {
  const { lessons, lesson, select } = useShelterLesson()
  const others = lessons.filter((item) => item.lesson.id !== lesson?.lesson.id)

  return (
    <section id="next-offline" className="flex flex-col gap-4 rounded-3xl border border-line bg-surface p-5 xl:p-7">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment xl:text-[22px] xl:tracking-[-0.22px]">
          {next.title}
        </h2>
        <p className="text-right text-xs leading-4 text-dim">{next.hint}</p>
      </div>
      {others.length === 0 && <p className="text-sm text-muted">{next.empty}</p>}
      <ul className="grid gap-3 md:grid-cols-3">
        {others.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              onClick={() => {
                select(item.lesson.id)
                document.getElementById('lesson-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
              }}
              className="flex w-full flex-col gap-1 rounded-2xl border border-line bg-surface-2/50 p-4 text-left hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            >
              <span className="text-xs leading-4 text-dim">
                {item.startsAt}–{item.endsAt}
              </span>
              <span className="text-[15px] leading-[22.5px] font-semibold text-parchment">{item.lesson.title}</span>
              <span className="pt-1 text-xs leading-4 text-dim">
                {item.lesson.modules.length} {pluralUk(item.lesson.modules.length, ['модуль', 'модулі', 'модулів'])} · {item.minutes} хв
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
