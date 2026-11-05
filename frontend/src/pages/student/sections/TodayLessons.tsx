import iconCheck from '@/assets/student/check-20.svg'
import iconBook from '@/assets/student/book.svg'
import { todayLessons } from '../content'
import type { LessonState } from '../content'

function LessonMark({ state }: { state: LessonState }) {
  if (state === 'now') {
    return <span className="rounded-md bg-accent px-2 py-0.5 text-[11px] leading-[16.5px] font-semibold text-oil">зараз</span>
  }
  if (state === 'done') {
    return <img src={iconCheck} alt="Пройдено" width={20} height={20} className="shrink-0" />
  }
  return <span className="text-[11px] leading-[16.5px] whitespace-nowrap text-dim">офлайн ✓</span>
}

export default function TodayLessons() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{todayLessons.title}</h2>
        <p className="max-w-[102px] text-right text-xs text-dim md:max-w-none">{todayLessons.hint}</p>
      </div>
      {/* TODO: відкривати урок за натисканням, коли зʼявиться сторінка уроку */}
      <ul className="grid gap-3 md:grid-cols-2">
        {todayLessons.items.map((item) => (
          <li
            key={item.name}
            className={`flex items-center gap-4 rounded-2xl border p-4 ${
              item.state === 'now' ? 'border-accent/50 bg-surface-2' : 'border-line bg-surface-2/50'
            }`}
          >
            <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft">
              <img src={iconBook} alt="" width={20} height={20} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-xs text-dim">{item.subject}</span>
              <span className="block truncate text-sm leading-[22.5px] font-semibold text-parchment">{item.name}</span>
              <span className="block pt-0.5 text-xs text-dim">{item.meta}</span>
            </span>
            <LessonMark state={item.state} />
          </li>
        ))}
      </ul>
    </section>
  )
}
