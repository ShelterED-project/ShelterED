import { todayLabel } from '@/shared/lib/date'

// Моків немає: там, де мають бути дані з API, стоїть заглушка «Сюди: …» з описом, що саме додати.
// Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

export type ChildId = 'child'

export const children: { id: ChildId; label: string; name: string }[] = [
  { id: 'child', label: 'Сюди: дитина', name: 'Сюди: імʼя дитини і клас' },
]

// Ім'я батьків беремо з сесії (useCurrentUser); кількість дітей дасть API.
export const parentRole = 'Батьки'

export const greeting = { hello: 'Вітаємо', date: todayLabel({ capitalize: true }) }

export const safetyStatus = {
  alert: 'Сюди: поточна тривога (час початку, область)',
  title: 'Сюди: де зараз дитина (в укритті / вдома)',
  text: 'Сюди: коли відмітилась і що відбувається на уроці',
  dataTime: 'Сюди: час, на який актуальні дані',
  note: 'Оновиться, щойно в школи зʼявиться звʼязок',
}

export type KpiIcon = 'book' | 'clock' | 'chart' | 'map'

export const kpis: { label: string; value: string; hint: string; icon: KpiIcon; accent?: boolean }[] = [
  { label: 'Уроків за тиждень', value: '—', hint: 'Сюди: проведено з усіх, з них в укритті', icon: 'book' },
  { label: 'Час навчання', value: '—', hint: 'Сюди: порівняння з минулим тижнем', icon: 'clock' },
  { label: 'Середній бал тестів', value: '—', hint: 'Сюди: кількість тестів', icon: 'chart' },
  { label: 'Незвідані теми', value: '—', hint: 'Сюди: що варто повторити', icon: 'map', accent: true },
]

export const week = {
  title: 'Навчання за тиждень',
  range: 'Сюди: тиждень',
  // Хвилини навчання; висота стовпчика в пікселях дорівнює значенню. Сюди: дані по днях.
  days: [
    { day: 'Пн', regular: 0, shelter: 0 },
    { day: 'Вт', regular: 0, shelter: 0 },
    { day: 'Ср', regular: 0, shelter: 0 },
    { day: 'Чт', regular: 0, shelter: 0 },
    { day: 'Пт', regular: 0, shelter: 0 },
  ],
  legend: { regular: 'звичайні уроки', shelter: 'уроки в укритті' },
}

export const homework = {
  title: 'Що повторити вдома',
  items: [{ title: 'Сюди: тема', note: 'предмет · коли пропущено' }],
  moleSays: 'Сюди: порада ШІ-репетитора, з чого почати.',
}

export type RollCallState = 'shelter' | 'safe' | 'none'

export const rollCall: {
  title: string
  rows: { day: string; alert: string; state: RollCallState; label: string; time: string }[]
} = {
  title: 'Журнал переклички',
  rows: [{ day: 'Сюди: день', alert: 'час тривоги', state: 'none', label: 'статус переклички', time: '—' }],
}

export const teacherMessage = {
  title: 'Від вчителя',
  initials: '—',
  author: 'Сюди: імʼя вчителя',
  time: '—',
  text: 'Сюди: текст повідомлення від вчителя.',
  reply: 'Відповісти',
}

export const visibility = {
  title: 'Що ви бачите',
  items: [
    { text: 'Статус переклички дитини', visible: true },
    { text: 'Прогрес і пропущені теми', visible: true },
    { text: 'Повідомлення від вчителя', visible: true },
    { text: 'Геолокацію — ми її не збираємо', visible: false },
    { text: 'Дані інших учнів класу', visible: false },
  ],
}

export type NavId = 'overview' | 'progress' | 'messages' | 'notifications' | 'settings'

export const sidebarNav: { id: NavId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'progress', label: 'Прогрес' },
  { id: 'messages', label: 'Повідомлення' },
  { id: 'notifications', label: 'Сповіщення' },
  { id: 'settings', label: 'Налаштування' },
]

export type TabId = 'overview' | 'progress' | 'chat' | 'more'

export const mobileTabs: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'progress', label: 'Прогрес' },
  { id: 'chat', label: 'Чат' },
  { id: 'more', label: 'Ще' },
]
