// TODO: тимчасові моки. Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

export type ChildId = 'olya' | 'marko'

export const children: { id: ChildId; label: string; name: string }[] = [
  { id: 'olya', label: 'Оля · 7-Б', name: 'Оля, 7-Б' },
  { id: 'marko', label: 'Марко · 3-А', name: 'Марко, 3-А' },
]

export const parentUser = { initials: 'НК', name: 'Наталія Ковальчук', role: 'Батьки · 2 дитини' }

export const greeting = { title: 'Вітаємо, Наталіє!', date: 'Вівторок, 14 жовтня' }

export const safetyStatus = {
  alert: 'Тривога з 10:14 · Львівська обл.',
  title: 'Оля в укритті школи',
  text: 'Відмітилась о 10:16 · урок алгебри продовжується офлайн',
  dataTime: 'дані на 10:16',
  note: 'Оновиться, щойно в школи зʼявиться звʼязок',
}

export type KpiIcon = 'book' | 'clock' | 'chart' | 'map'

export const kpis: { label: string; value: string; hint: string; icon: KpiIcon; accent?: boolean }[] = [
  { label: 'Уроків за тиждень', value: '9 / 12', hint: '3 — в укритті', icon: 'book' },
  { label: 'Час навчання', value: '3,7 год', hint: '+25 хв до минулого', icon: 'clock' },
  { label: 'Середній бал тестів', value: '84%', hint: '7 тестів', icon: 'chart' },
  { label: 'Незвідані теми', value: '2', hint: 'варто повторити', icon: 'map', accent: true },
]

export const week = {
  title: 'Навчання за тиждень',
  range: '13–17 жовтня',
  // Хвилини навчання; висота стовпчика в пікселях дорівнює значенню
  days: [
    { day: 'Пн', regular: 90, shelter: 0 },
    { day: 'Вт', regular: 60, shelter: 60 },
    { day: 'Ср', regular: 120, shelter: 0 },
    { day: 'Чт', regular: 30, shelter: 30 },
    { day: 'Пт', regular: 90, shelter: 0 },
  ],
  legend: { regular: 'звичайні уроки', shelter: 'уроки в укритті' },
}

export const homework = {
  title: 'Що повторити вдома',
  items: [
    { title: 'Десяткові дроби', note: 'Алгебра · пропущено під час тривоги 14.10' },
    { title: 'Прислівник', note: 'Українська мова · пропущено 16.10' },
  ],
  moleSays: 'Почніть із «Десяткових» — 2 модулі по 5 хвилин. Можна без інтернету.',
}

export type RollCallState = 'shelter' | 'safe' | 'none'

export const rollCall: {
  title: string
  rows: { day: string; alert: string; state: RollCallState; label: string; time: string }[]
} = {
  title: 'Журнал переклички',
  rows: [
    { day: 'Вт, 14.10', alert: '10:14–11:02', state: 'shelter', label: 'в укритті', time: '10:16' },
    { day: 'Пн, 13.10', alert: '—', state: 'none', label: 'тривог не було', time: '—' },
    { day: 'Пт, 10.10', alert: '08:40–09:15', state: 'safe', label: 'в безпеці вдома', time: '08:42' },
    { day: 'Чт, 09.10', alert: '12:05–13:30', state: 'shelter', label: 'в укритті', time: '12:07' },
  ],
}

export const teacherMessage = {
  title: 'Від вчителя',
  initials: 'ОК',
  author: 'Олена Коваль',
  time: '11:20',
  text: 'Сьогодні клас пройшов алгебру в укритті. Тест перенесено на четвер — повторювати нічого не треба.',
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
