import { useEffect, useMemo, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '@/shared/db/db'
import type { PackLesson, ScheduleItem } from '@/shared/db/packTypes'

export type LessonStatus = 'now' | 'next' | 'done'

export interface TodayLesson {
  /** Позиція в розкладі дня: ключ для списків (один урок може стояти двічі) */
  key: string
  item: ScheduleItem
  lesson: PackLesson
  status: LessonStatus
  /** Сумарна тривалість модулів, хв */
  minutes: number
  /** Початок і кінець за місцевим часом школи, HH:MM */
  startsAt: string
  endsAt: string
}

export interface TodayPack {
  /** null, поки пакет за сьогодні не збережено на пристрої */
  lessons: TodayLesson[] | null
  /** Коли збудовано збережений пакет */
  builtAt: string | null
}

/** Як часто перераховувати «зараз / далі»: лише таймер у памʼяті, без мережі. */
const TICK_MS = 60_000

/** Сьогоднішня дата пристрою у форматі пакета, YYYY-MM-DD. */
function todayKey(): string {
  return new Date().toLocaleDateString('sv-SE')
}

function hhmm(time: string | null): string {
  return time ? time.slice(0, 5) : '—'
}

function statusAt(item: ScheduleItem, now: number): LessonStatus {
  const start = item.starts_at_utc ? Date.parse(item.starts_at_utc) : Infinity
  const end = item.ends_at_utc ? Date.parse(item.ends_at_utc) : Infinity
  return now >= end ? 'done' : now >= start ? 'now' : 'next'
}

/**
 * Уроки на сьогодні зі збереженого пакета «Рюкзака». Читає лише IndexedDB (принцип 1):
 * працює без мережі, оновлюється, коли syncPacks докачає новий пакет.
 */
export function useTodayPack(): TodayPack {
  const pack = useLiveQuery(() => db.packs.where('pack_date').equals(todayKey()).first(), [])
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(id)
  }, [])

  return useMemo((): TodayPack => {
    if (!pack) return { lessons: null, builtAt: null }
    const lessons: TodayLesson[] = []
    for (const item of pack.schedule) {
      const lesson = pack.lessons.find((l) => l.id === item.lesson_id)
      if (!lesson) continue
      lessons.push({
        key: `${item.slot_id ?? item.override_id ?? item.lesson_id}-${item.starts_at ?? ''}`,
        item,
        lesson,
        status: statusAt(item, now),
        minutes: lesson.modules.reduce((sum, m) => sum + m.duration_min, 0),
        startsAt: hhmm(item.starts_at),
        endsAt: hhmm(item.ends_at),
      })
    }
    return { lessons, builtAt: pack.built_at }
  }, [pack, now])
}

/** Урок, що йде зараз, а якщо його немає, найближчий наступний. */
export function pickCurrentLesson(lessons: TodayLesson[] | null): TodayLesson | null {
  if (!lessons) return null
  return lessons.find((l) => l.status === 'now') ?? lessons.find((l) => l.status === 'next') ?? null
}
