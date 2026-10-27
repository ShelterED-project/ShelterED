// TODO: тимчасові моки. Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

export const adminUser = { initials: 'НП', name: 'Наталія Поліщук', role: 'Заступниця директора' }

export const school = { name: 'Ліцей №12, м. Харків', subtitle: 'Панель адміністрації', date: 'вівторок, 14 жовтня' }

export const alertBanner = {
  title: 'Тривога з 10:14 · 312 з 486 учнів відмітились в укритті',
  text: 'Дані про розташування укриттів видно лише адміністрації.',
  journal: 'Журнал тривог',
}

export type KpiIcon = 'shelter' | 'classes' | 'bell' | 'wifi'

export const kpis: { label: string; value: string; hint: string; icon: KpiIcon; accent?: boolean }[] = [
  { label: 'В укритті зараз', value: '312 / 486', hint: '64% учнів відмітились', icon: 'shelter', accent: true },
  { label: 'Класів', value: '18', hint: '42 вчителі', icon: 'classes' },
  { label: 'Тривог за тиждень', value: '9', hint: '11 год 40 хв загалом', icon: 'bell' },
  { label: 'Локальні сервери', value: '3 / 4', hint: '1 офлайн — 9-В', icon: 'wifi' },
]

export const classes = {
  title: 'Класи в укритті',
  all: 'Усі класи',
  rows: [
    { name: '5-А', present: 26, total: 28 },
    { name: '6-Б', present: 27, total: 30 },
    { name: '7-А', present: 21, total: 25 },
    { name: '7-Б', present: 22, total: 27 },
    { name: '8-А', present: 29, total: 29 },
    { name: '9-В', present: 18, total: 26 },
  ],
}

export const users = {
  title: 'Користувачі',
  summary: '486 учнів · 42 вчителі',
  items: [
    { initials: 'ОК', name: 'Олена Коваль', role: 'Вчитель · 7-Б' },
    { initials: 'ВГ', name: 'Віктор Гончар', role: 'Вчитель · 9-В' },
    { initials: 'НП', name: 'Наталія Поліщук', role: 'Адміністрація' },
  ],
  invite: 'Запросити вчителя',
}

export const alarms = {
  title: 'Журнал тривог',
  export: 'Експорт CSV',
  rows: [
    { date: '14.10', start: '10:14', end: '—', duration: 'триває', affected: 'усі класи', ongoing: true },
    { date: '13.10', start: '22:40', end: '00:55', duration: '2 год 15 хв', affected: 'поза уроками', ongoing: false },
    { date: '13.10', start: '09:05', end: '10:20', duration: '1 год 15 хв', affected: '18 класів', ongoing: false },
    { date: '11.10', start: '14:30', end: '15:10', duration: '40 хв', affected: '12 класів', ongoing: false },
    { date: '10.10', start: '08:10', end: '09:40', duration: '1 год 30 хв', affected: '18 класів', ongoing: false },
  ],
}

export type NavId = 'overview' | 'classes' | 'users' | 'alarms' | 'servers' | 'settings'

export const sidebarNav: { id: NavId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'classes', label: 'Класи' },
  { id: 'users', label: 'Користувачі' },
  { id: 'alarms', label: 'Журнал тривог' },
  { id: 'servers', label: 'Локальні сервери' },
  { id: 'settings', label: 'Налаштування школи' },
]

export type TabId = 'overview' | 'classes' | 'alarms' | 'more'

export const mobileTabs: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'classes', label: 'Класи' },
  { id: 'alarms', label: 'Тривоги' },
  { id: 'more', label: 'Ще' },
]
