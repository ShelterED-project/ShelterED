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
  subtitle: todayLabel({ capitalize: true }),
}

export const shelterMode = 'Режим укриття'

export const alertNotice = {
  title: 'Триває повітряна тривога',
  drillTitle: 'Триває тренувальна тривога',
  open: 'Режим укриття',
}

export const lessonBanner = {
  now: 'Урок зараз',
  next: 'Наступний урок',
  none: 'На сьогодні уроків немає',
  noPack: 'Пакет на сьогодні ще не збережено',
  noPackText: 'Підключись до мережі один раз, і уроки збережуться на пристрої.',
  noLessonsText: 'Відпочивай або повтори пройдене.',
  open: 'Відкрити урок',
  breathe: 'Подихати',
}

export type RouteNodeKind = 'done' | 'todo' | 'current'
export type RouteNodeId = 'natural' | 'fractions' | 'decimals' | 'percent'

/** Вузли мапи: позиції заведені для чотирьох точок, тож показуємо до чотирьох предметів. */
export const ROUTE_NODE_IDS: RouteNodeId[] = ['natural', 'fractions', 'decimals', 'percent']

export const route = {
  title: 'Мій маршрут',
  range: (done: number, total: number) => `Пройдено ${done} з ${total} уроків`,
  gap: 'прогалина',
  moleStart: (subject: string) => `Почни з предмета «${subject}».`,
  moleDone: 'Усе, що є, пройдено. Молодець!',
  moleEmpty: 'Пройди перший урок, і я покажу, куди йти далі.',
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

export const sync = {
  noPack: 'Пакет на сьогодні ще не збережено',
  saved: (time: string) => `Пакет на сьогодні збережено · оновлено о ${time}`,
}

export const calm = { title: 'Хвилинка спокою', text: 'Дихання з вогником · 2 хв' }

export type LessonState = 'now' | 'offline' | 'done'

export const todayLessons = {
  title: 'Уроки на сьогодні',
  hintSaved: 'усе збережено офлайн',
  hintMissing: 'пакет ще не збережено',
  empty: 'На сьогодні уроків немає.',
  noPack: 'Пакет на сьогодні ще не збережено. Підключись до мережі один раз, і уроки зʼявляться тут.',
}

export type NavId = 'route' | 'lessons' | 'calm' | 'me' | 'settings'

/** Розділи з готовою сторінкою мають маршрут; решта поки без переходу. */
export const navRoutes: Partial<Record<NavId, string>> = {
  route: '/student',
  lessons: '/student/lessons',
}

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
