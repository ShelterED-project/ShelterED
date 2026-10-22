// TODO: тимчасові моки. Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).
// Кількість записів у черзі не мок: її дає useOutboxCount.

export const studentUser = { initials: 'ОК', name: 'Оля Ковальчук', role: 'Учениця · 7-Б' }

export const greeting = { title: 'Привіт, Олю!', date: 'Вівторок, 14 жовтня', subtitle: 'Вівторок, 14 жовтня · 7-Б' }

export const shelterMode = 'Режим укриття'

export const lessonBanner = {
  eyebrow: 'Тривога з 10:14 · урок продовжується',
  title: 'Алгебра: лінійні рівняння',
  text: '3 картки · 1 тест · ≈ 12 хв · підготувала Олена Коваль',
  open: 'Відкрити урок',
  breathe: 'Подихати',
}

export type RouteNodeKind = 'done' | 'todo' | 'current'
export type RouteNodeId = 'natural' | 'fractions' | 'decimals' | 'percent'

export const route = {
  title: 'Твій маршрут: математика',
  range: '5 клас → 7 клас',
  nodes: [
    { id: 'natural', kind: 'done', label: 'Натуральні числа' },
    { id: 'fractions', kind: 'done', label: 'Дроби' },
    { id: 'decimals', kind: 'todo', label: 'Десяткові', badge: 'незвідано' },
    { id: 'percent', kind: 'current', label: 'Відсотки · ти тут' },
  ] as { id: RouteNodeId; kind: RouteNodeKind; label: string; badge?: string }[],
  moleSays: 'Спершу повернімось до «Десяткових» — це 2 короткі модулі.',
  go: 'Піти',
  breatheFirst: 'Спершу подихати',
}

export const checkIn = {
  title: 'Перекличка класу',
  text: 'Відміться, щоб Олена Іванівна знала, що ти в безпеці.',
  shelter: 'Я в укритті',
  safe: 'Я в безпеці вдома',
  offlineNote: 'Без мережі — відправимо, щойно зʼявиться зв’язок',
  saved: 'Відмітку збережено',
}

export const sync = { package: 'Пакет на сьогодні: 42 МБ · збережено' }

export const calm = { title: 'Хвилинка спокою', text: 'Дихання з вогником · 2 хв' }

export type LessonState = 'now' | 'offline' | 'done'

export const todayLessons: {
  title: string
  items: { subject: string; name: string; meta: string; state: LessonState }[]
  hint: string
} = {
  title: 'Уроки на сьогодні',
  hint: 'усі збережено офлайн',
  items: [
    { subject: 'Алгебра', name: 'Лінійні рівняння', meta: '12 хв · 3 картки · тест', state: 'now' },
    { subject: 'Українська мова', name: 'Прислівник: правопис', meta: '8 хв · картки', state: 'offline' },
    { subject: 'Історія України', name: 'Київська Русь: князі', meta: '10 хв · відео з субтитрами', state: 'offline' },
    { subject: 'Природознавство', name: 'Вода в природі', meta: '5 хв · картки', state: 'done' },
  ],
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
