import { useEffect, useMemo, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '@/shared/db/db'
import type { Pack, PackLesson, ScheduleItem } from '@/shared/db/packTypes'

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
 * Найновіша версія пакета кожного дня. Після заміни уроку на день приходить новий пакет з іншим id;
 * syncPacks прибирає старий, щойно новий збережено, а до того (чи на старих пристроях) читаємо
 * лише новіший: за version, потім за built_at.
 */
export function latestPerDay(packs: Pack[]): Pack[] {
  const byDate = new Map<string, Pack>()
  for (const pack of packs) {
    const current = byDate.get(pack.pack_date)
    if (
      !current ||
      pack.version > current.version ||
      (pack.version === current.version && pack.built_at > current.built_at)
    ) {
      byDate.set(pack.pack_date, pack)
    }
  }
  return [...byDate.values()].sort((a, b) => a.pack_date.localeCompare(b.pack_date))
}

/** Пакет дня (YYYY-MM-DD) з пристрою, найновіша версія. */
export async function packOn(date: string): Promise<Pack | undefined> {
  return latestPerDay(await db.packs.where('pack_date').equals(date).toArray())[0]
}

/**
 * Уроки на сьогодні зі збереженого пакета «Рюкзака». Читає лише IndexedDB (принцип 1):
 * працює без мережі, оновлюється, коли syncPacks докачає новий пакет.
 */
export function useTodayPack(): TodayPack {
  const pack = useLiveQuery(() => packOn(todayKey()), [])
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(id)
  }, [])

  return useMemo(
    (): TodayPack => (pack ? { lessons: packLessons(pack, now), builtAt: pack.built_at } : { lessons: null, builtAt: null }),
    [pack, now],
  )
}

function packLessons(pack: Pack, now: number): TodayLesson[] {
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
  return lessons
}

export interface NextPackDay {
  /** День пакета, YYYY-MM-DD */
  date: string
  lessons: TodayLesson[]
}

/**
 * Найближчий наступний день з уроками в «Рюкзаку» (після сьогодні): для списку «Завтра».
 * null, поки такого пакета на пристрої немає.
 */
export function useNextPackDay(): NextPackDay | null {
  const pack = useLiveQuery(
    async () =>
      latestPerDay(await db.packs.where('pack_date').above(todayKey()).toArray()).find((p) =>
        p.schedule.some((item) => item.lesson_id !== null),
      ),
    [],
  )
  // День ще не настав, тож усі уроки «далі»: статус рахуємо від нульового часу.
  return useMemo(() => (pack ? { date: pack.pack_date, lessons: packLessons(pack, 0) } : null), [pack])
}

/** Урок, що йде зараз, а якщо його немає, найближчий наступний. */
export function pickCurrentLesson(lessons: TodayLesson[] | null): TodayLesson | null {
  if (!lessons) return null
  return lessons.find((l) => l.status === 'now') ?? lessons.find((l) => l.status === 'next') ?? null
}
