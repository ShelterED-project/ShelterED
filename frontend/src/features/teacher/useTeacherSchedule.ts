import { useEffect, useMemo, useState } from 'react'
import { skipToken } from '@reduxjs/toolkit/query/react'
import { useClassesQuery, useClassScheduleQuery, useLessonsQuery, useSubjectsQuery } from './teacherApi'

export type ScheduleRowStatus = 'done' | 'now' | 'next'

export interface ScheduleRow {
  key: string
  /** HH:MM місцевого часу школи; '—' для додаткового уроку без часу */
  startsAt: string
  endsAt: string
  subject: string
  /** На цей слот призначено урок */
  hasLesson: boolean
  /** Назва призначеного уроку; null — не призначено або урок іншого вчителя (назви не знаємо) */
  lessonTitle: string | null
  status: ScheduleRowStatus
}

export interface ScheduleDayRows {
  /** YYYY-MM-DD, дата школи */
  date: string
  rows: ScheduleRow[]
}

/** «Зараз / минув / далі» перераховується локальним таймером, без запитів. */
const TICK_MS = 60_000

function hhmm(time: string | null): string {
  return time ? time.slice(0, 5) : '—'
}

function statusAt(startUtc: string | null, endUtc: string | null, now: number): ScheduleRowStatus {
  const start = startUtc ? Date.parse(startUtc) : Infinity
  const end = endUtc ? Date.parse(endUtc) : Infinity
  return now >= end ? 'done' : now >= start ? 'now' : 'next'
}

/**
 * Розклад першого класу вчителя на `days` днів від сьогодні: предмети й призначені уроки.
 * Розклад змінюється рідко, тож без опитування: дані беруться при відкритті сторінки.
 */
export function useTeacherSchedule(days = 1) {
  const classes = useClassesQuery()
  const classId = classes.data?.[0]?.id
  const schedule = useClassScheduleQuery(classId ? { classId, days } : skipToken)
  const subjects = useSubjectsQuery()
  // Назви уроків є лише для власних уроків вчителя; для чужих показуємо тільки предмет.
  const lessons = useLessonsQuery()
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(id)
  }, [])

  const dayRows = useMemo((): ScheduleDayRows[] | null => {
    if (!schedule.data) return null
    const subjectName = new Map((subjects.data ?? []).map((s) => [s.id, s.name]))
    const lessonTitle = new Map((lessons.data ?? []).map((l) => [l.id, l.title]))
    return schedule.data.days.map((day) => ({
      date: day.date,
      rows: day.items.map((item, i) => ({
        key: `${item.slot_id ?? item.override_id ?? i}-${item.starts_at ?? ''}`,
        startsAt: hhmm(item.starts_at),
        endsAt: hhmm(item.ends_at),
        subject: subjectName.get(item.subject_id) ?? '—',
        hasLesson: item.lesson_id !== null,
        lessonTitle: item.lesson_id ? (lessonTitle.get(item.lesson_id) ?? null) : null,
        status: statusAt(item.starts_at_utc, item.ends_at_utc, now),
      })),
    }))
  }, [schedule.data, subjects.data, lessons.data, now])

  return {
    days: dayRows,
    /** Перший день (сьогодні) — для картки на огляді */
    rows: dayRows?.[0]?.rows ?? null,
    isLoading: classes.isLoading || schedule.isLoading,
    isOffline: classes.isError || schedule.isError,
  }
}
