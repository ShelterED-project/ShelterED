import { useMemo, useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '@/shared/db/db'
import { useStudentProgress } from './useStudentProgress'

export type RouteStatus = 'done' | 'current' | 'todo'

export interface RouteLesson {
  lessonId: string
  title: string
  /** Назва предмета з прогресу сервера; для уроку, якого там ще немає, невідома */
  subject: string | null
  /** Початок і кінець за місцевим часом школи, HH:MM */
  startsAt: string | null
  endsAt: string | null
  status: RouteStatus
}

function hhmm(time: string | null): string | null {
  return time ? time.slice(0, 5) : null
}

/**
 * Маршрут учня на сьогодні: уроки з сьогоднішнього пакета «Рюкзака» в порядку розкладу.
 * Усе з пристрою, тож працює без мережі. Пройдено: за сервером або за локальним прогресом
 * (ще не синхронізованим). Поточний — перший непройдений.
 */
export function useLessonRoute() {
  const { progress } = useStudentProgress()
  // Дату фіксуємо при відкритті: маршрут не перебудовується посеред перегляду.
  const [today] = useState(() => new Date().toLocaleDateString('sv-SE'))
  // undefined — ще читаємо IndexedDB, null — пакета на сьогодні немає.
  const pack = useLiveQuery(async () => (await db.packs.where('pack_date').equals(today).first()) ?? null, [today])
  const local = useLiveQuery(() => db.progress.toArray(), [])

  const lessons = useMemo((): RouteLesson[] => {
    if (!pack) return []
    const server = new Map((progress?.lessons ?? []).map((l) => [l.lesson_id, l]))
    const localDone = new Set((local ?? []).map((r) => r.id))
    const byId = new Map(pack.lessons.map((l) => [l.id, l]))

    const items = [...pack.schedule]
      .sort((a, b) => (a.starts_at ?? '').localeCompare(b.starts_at ?? ''))
      .flatMap((item) => {
        const lesson = item.lesson_id ? byId.get(item.lesson_id) : undefined
        return lesson ? [{ item, lesson }] : []
      })
      // Один урок може стояти двічі за день: на маршруті — один раз, на першому місці.
      .filter(({ lesson }, i, all) => all.findIndex((x) => x.lesson.id === lesson.id) === i)
      .map(({ item, lesson }) => ({
        lessonId: lesson.id,
        title: lesson.title,
        subject: server.get(lesson.id)?.subject_name ?? null,
        startsAt: hhmm(item.starts_at),
        endsAt: hhmm(item.ends_at),
        done:
          (server.get(lesson.id)?.progress_pct ?? 0) >= 100 ||
          (lesson.modules.length > 0 && lesson.modules.every((m) => localDone.has(m.id))),
      }))

    const currentIndex = items.findIndex((item) => !item.done)
    return items.map(({ done, ...item }, i) => ({
      ...item,
      status: done ? 'done' : i === currentIndex ? 'current' : 'todo',
    }))
  }, [pack, progress, local])

  return {
    lessons,
    /** false, поки пакет на сьогодні не збережено на пристрої */
    hasPack: Boolean(pack),
    isLoading: pack === undefined,
  }
}
