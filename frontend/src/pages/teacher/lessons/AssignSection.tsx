import { useState } from 'react'
import { skipToken } from '@reduxjs/toolkit/query/react'
import { useAssignLessonMutation, useUnassignLessonMutation } from '@/features/teacher/lessonEditorApi'
import type { LessonOut } from '@/features/teacher/lessonEditorApi'
import { useClassesQuery, useClassScheduleQuery, useLessonsQuery } from '@/features/teacher/teacherApi'
import type { ScheduleItem } from '@/features/teacher/teacherApi'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import { card, primaryButton, secondaryButton, dangerButton } from './styles'
import { useAction } from './useAction'

/** Скільки днів наперед шукаємо слоти: максимум, який віддає сервер. */
const DAYS = 14
/** Скільки найближчих слотів показуємо. */
const LIMIT = 10

interface Slot {
  key: string
  date: string
  slotId: string
  item: ScheduleItem
}

function slotLabel(date: string, item: ScheduleItem): string {
  const day = new Date(`${date}T12:00:00Z`).toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'short' })
  return item.starts_at ? `${day}, ${item.starts_at.slice(0, 5)}` : day
}

function SlotRow({
  classId,
  lesson,
  slot,
  otherTitle,
  now,
}: {
  classId: string
  lesson: LessonOut
  slot: Slot
  otherTitle: string | null
  now: number
}) {
  const t = editor.assign
  const [assign] = useAssignLessonMutation()
  const [unassign] = useUnassignLessonMutation()
  const action = useAction()
  const mine = slot.item.lesson_id === lesson.id
  const taken = slot.item.lesson_id !== null && !mine
  const past = slot.item.ends_at_utc !== null && Date.parse(slot.item.ends_at_utc) < now

  return (
    <li className="flex flex-col gap-2 border-t border-line-soft py-3 first:border-t-0 md:flex-row md:items-center">
      <div className="min-w-0 flex-1">
        <p className={`text-[15px] leading-[22.5px] font-medium ${past ? 'text-dim' : 'text-parchment'}`}>
          {slotLabel(slot.date, slot.item)}
        </p>
        <p className={`text-xs ${mine ? 'font-semibold text-safe' : taken ? 'text-dim' : 'text-accent'}`}>
          {mine ? t.thisLesson : taken ? t.other(otherTitle) : t.free}
        </p>
        {action.error && (
          <p role="alert" className="text-sm font-semibold text-accent">
            {action.error}
          </p>
        )}
      </div>
      {mine ? (
        <button
          type="button"
          disabled={action.busy}
          onClick={() => void action.run(() => unassign({ classId, slotId: slot.slotId, date: slot.date }).unwrap())}
          className={dangerButton}
        >
          {action.busy && <Spinner />}
          {t.unassign}
        </button>
      ) : (
        <button
          type="button"
          disabled={action.busy}
          onClick={() =>
            void action.run(() => assign({ classId, slotId: slot.slotId, date: slot.date, lessonId: lesson.id }).unwrap())
          }
          className={taken ? secondaryButton : primaryButton}
        >
          {action.busy && <Spinner />}
          {taken ? t.replace : t.assignTo}
        </button>
      )}
    </li>
  )
}

/**
 * Призначення опублікованого уроку на найближчі слоти його предмета в розкладі першого класу вчителя.
 * Призначити можна лише на слот (регулярний чи заміну), не на додатковий урок без слота.
 */
export default function AssignSection({ lesson }: { lesson: LessonOut }) {
  const t = editor.assign
  const classes = useClassesQuery()
  const teacherClass = classes.data?.[0]
  const schedule = useClassScheduleQuery(teacherClass ? { classId: teacherClass.id, days: DAYS } : skipToken)
  const lessons = useLessonsQuery()
  const titles = new Map((lessons.data ?? []).map((l) => [l.id, l.title]))
  const published = lesson.status === 'published'
  // Час на момент відкриття: щоб приглушити вже минулі слоти, без таймера.
  const [now] = useState(() => Date.now())

  const slots: Slot[] = []
  for (const day of schedule.data?.days ?? []) {
    day.items.forEach((item, i) => {
      if (item.subject_id !== lesson.subject_id || !item.slot_id) return
      slots.push({ key: `${day.date}-${item.slot_id}-${i}`, date: day.date, slotId: item.slot_id, item })
    })
  }
  // Уже призначені на цей урок слоти показуємо завжди, решту — лише найближчі.
  const shown = slots.filter((s, i) => i < LIMIT || s.item.lesson_id === lesson.id)

  return (
    <section className={card}>
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.title}</h2>
        <p className="text-sm text-dim">{teacherClass ? t.hint(teacherClass.name) : t.noClass}</p>
      </div>
      {!published ? (
        <p className="text-sm text-muted">
          {slots.some((s) => s.item.lesson_id === lesson.id) ? t.unpublishedNote : t.needPublish}
        </p>
      ) : !schedule.data ? (
        <p role="status" className="text-sm text-muted">
          {schedule.isLoading || classes.isLoading ? t.loading : t.empty}
        </p>
      ) : shown.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        teacherClass && (
          <ul>
            {shown.map((slot) => (
              <SlotRow
                key={slot.key}
                classId={teacherClass.id}
                lesson={lesson}
                slot={slot}
                otherTitle={slot.item.lesson_id ? (titles.get(slot.item.lesson_id) ?? null) : null}
                now={now}
              />
            ))}
          </ul>
        )
      )}
    </section>
  )
}
