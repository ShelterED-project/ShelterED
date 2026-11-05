import { todayLabel } from '@/shared/lib/date'

// Моків немає: там, де мають бути дані з API, стоїть заглушка «Сюди: …» з описом, що саме додати.
// Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).
// Кількість записів у черзі не заглушка: її дає useOutboxCount.

// Ім'я учня беремо з сесії (useCurrentUser); клас дасть API.
export const studentRole = 'Учень'

export const greeting = {
  hello: 'Привіт',
  date: todayLabel({ capitalize: true }),
  subtitle: `${todayLabel({ capitalize: true })} · Сюди: клас`,
}

export const shelterMode = 'Режим укриття'

export const lessonBanner = {
  eyebrow: 'Сюди: тривога (час початку) і що з уроком',
  title: 'Сюди: назва поточного уроку',
  text: 'Сюди: кількість карток і тестів, тривалість, хто підготував',
  open: 'Відкрити урок',
  breathe: 'Подихати',
}

export type RouteNodeKind = 'done' | 'todo' | 'current'
export type RouteNodeId = 'natural' | 'fractions' | 'decimals' | 'percent'

export const route = {
  title: 'Сюди: маршрут предмета',
  range: 'Сюди: від якого класу до якого',
  // Сюди: теми маршруту з бекенда; id і kind задають позицію й вигляд вузла на мапі.
  nodes: [
    { id: 'natural', kind: 'done', label: 'Сюди: тема 1' },
    { id: 'fractions', kind: 'done', label: 'Сюди: тема 2' },
    { id: 'decimals', kind: 'todo', label: 'Сюди: тема 3', badge: 'статус' },
    { id: 'percent', kind: 'current', label: 'Сюди: поточна тема' },
  ] as { id: RouteNodeId; kind: RouteNodeKind; label: string; badge?: string }[],
  moleSays: 'Сюди: порада ШІ-репетитора, з чого почати.',
  go: 'Піти',
  breatheFirst: 'Спершу подихати',
}

export const checkIn = {
  title: 'Перекличка класу',
  text: 'Відміться, щоб вчитель знав, що ти в безпеці.',
  shelter: 'Я в укритті',
  safe: 'Я в безпеці вдома',
  offlineNote: 'Без мережі — відправимо, щойно зʼявиться зв’язок',
  saved: 'Відмітку збережено',
}

export const sync = { package: 'Сюди: розмір пакета на сьогодні і чи збережено' }

export const calm = { title: 'Хвилинка спокою', text: 'Дихання з вогником · 2 хв' }

export type LessonState = 'now' | 'offline' | 'done'

export const todayLessons: {
  title: string
  items: { subject: string; name: string; meta: string; state: LessonState }[]
  hint: string
} = {
  title: 'Уроки на сьогодні',
  hint: 'Сюди: чи все збережено офлайн',
  items: [{ subject: 'Сюди: предмет', name: 'назва уроку', meta: 'тривалість · з чого складається', state: 'offline' }],
}

export type NavId = 'route' | 'lessons' | 'calm' | 'me' | 'settings'

export const sidebarNav: { id: NavId; label: string }[] = [
  { id: 'route', label: 'Маршрут' },
  { id: 'lessons', label: 'Уроки' },
  { id: 'calm', label: 'Спокій' },
  { id: 'me', label: 'Я' },
  { id: 'settings', label: 'Налаштування' },
]

export type TabId = Exclude<NavId, 'settings'>

export const mobileTabs: { id: TabId; label: string }[] = [
  { id: 'route', label: 'Маршрут' },
  { id: 'lessons', label: 'Уроки' },
  { id: 'calm', label: 'Спокій' },
  { id: 'me', label: 'Я' },
]
