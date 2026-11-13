import { useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router'
import iconCheck from '@/assets/landing/icon-check.svg'
import mole from '@/assets/landing/mole.svg'
import iconPin from '@/assets/student/pin-sm.svg'
import { useLessonRoute } from '@/features/student/useLessonRoute'
import type { RouteLesson } from '@/features/student/useLessonRoute'
import { route } from '../content'

function Marker({ status }: { status: RouteLesson['status'] }) {
  if (status === 'done') {
    return (
      <span className="relative z-10 flex size-9 shrink-0 items-center justify-center rounded-full bg-accent">
        <img src={iconCheck} alt="" width={14} height={14} />
      </span>
    )
  }
  if (status === 'current') {
    return (
      <span className="relative z-10 flex size-9 shrink-0 items-center justify-center rounded-full border-4 border-parchment bg-oil">
        <span className="size-7 rounded-full shadow-[0_0_20px_4px_rgba(242,178,92,0.4)]" />
      </span>
    )
  }
  return <span className="relative z-10 size-9 shrink-0 rounded-full border-2 border-dashed border-muted bg-surface" />
}

function RouteItem({ lesson, isLast }: { lesson: RouteLesson; isLast: boolean }) {
  const when = lesson.startsAt ? `${lesson.startsAt}–${lesson.endsAt ?? ''}` : null
  const body = (
    <span className="min-w-0 flex-1">
      <span
        className={`block text-[15px] leading-[22.5px] font-semibold ${
          lesson.status === 'done' ? 'text-muted' : 'text-parchment'
        }`}
      >
        <span className="sr-only">{route.statusLabel[lesson.status]}: </span>
        {lesson.title}
      </span>
      <span className="block text-xs leading-4 text-dim">{[when, lesson.subject].filter(Boolean).join(' · ')}</span>
    </span>
  )

  return (
    <li
      data-current={lesson.status === 'current' || undefined}
      aria-current={lesson.status === 'current' ? 'step' : undefined}
      className="relative flex gap-3"
    >
      {/* Лінія стежки до наступного уроку; пройдена частина підсвічена. */}
      {!isLast && (
        <span
          aria-hidden="true"
          className={`absolute top-9 bottom-0 left-[17px] w-0.5 ${lesson.status === 'done' ? 'bg-accent' : 'bg-line'}`}
        />
      )}
      <Marker status={lesson.status} />
      {/* Урок сьогоднішнього пакета завжди є на пристрої, тож відкривається й без мережі. */}
      <Link
        to={`/student/lesson?lesson=${lesson.lessonId}`}
        className={`mb-3 flex min-w-0 flex-1 items-center gap-2 rounded-xl px-3 py-1.5 hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
          lesson.status === 'current' ? 'bg-surface-2' : ''
        }`}
      >
        {body}
      </Link>
    </li>
  )
}

export default function RouteSection({ className = '' }: { className?: string }) {
  const { lessons, hasPack, isLoading } = useLessonRoute()
  const navigate = useNavigate()
  const listRef = useRef<HTMLDivElement>(null)
  const current = lessons.find((l) => l.status === 'current')
  const done = lessons.filter((l) => l.status === 'done').length

  // Показуємо поточний урок одразу: прокручуємо лише сам список, не сторінку.
  useEffect(() => {
    const box = listRef.current
    const item = box?.querySelector<HTMLElement>('[data-current]')
    if (box && item) box.scrollTop = Math.max(0, item.offsetTop - box.clientHeight / 3)
  }, [current?.lessonId])

  const moleSays = isLoading
    ? route.loading
    : !hasPack
      ? route.moleNoPack
      : lessons.length === 0
        ? route.moleEmpty
        : current
          ? route.moleStart(current.title)
          : route.moleDone

  return (
    <section className={`flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 xl:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{route.title}</h2>
        <p className="shrink-0 text-xs text-dim">{lessons.length > 0 ? route.range(done, lessons.length) : ''}</p>
      </div>

      {lessons.length > 0 && (
        <div
          ref={listRef}
          className="relative max-h-[324px] overflow-y-auto rounded-[18px] border border-line bg-oil/40 p-4 md:max-h-[364px] xl:max-h-[404px]"
        >
          <ol>
            {lessons.map((lesson, i) => (
              <RouteItem key={lesson.lessonId} lesson={lesson} isLast={i === lessons.length - 1} />
            ))}
          </ol>
        </div>
      )}

      <div className="flex items-end gap-3 pt-1">
        <img
          src={mole}
          alt="Кріт — маскот ShelterED"
          width={80}
          height={80}
          className="size-20 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]"
        />
        <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[22px] leading-[1.15] font-semibold text-parchment">
          {moleSays}
        </p>
      </div>

      {/* TODO: вправа для дихання, коли зʼявиться відповідна сторінка */}
      <div className="flex flex-wrap gap-2 md:pl-[92px]">
        {current && (
          <button
            type="button"
            onClick={() => navigate(`/student/lesson?lesson=${current.lessonId}`)}
            className="h-11 rounded-[10px] bg-accent px-5 text-sm font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
          >
            {route.go}
          </button>
        )}
        <button
          type="button"
          className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-5 text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <img src={iconPin} alt="" width={16} height={16} />
          {route.breatheFirst}
        </button>
      </div>
    </section>
  )
}
