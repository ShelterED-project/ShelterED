import { todayLabel } from '@/shared/lib/date'

// Моків немає: там, де мають бути дані з API, стоїть заглушка «Сюди: …» з описом, що саме додати.
// Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

// Ім'я адміна беремо з сесії (useCurrentUser); посади в бекенді немає.
export const adminRole = 'Адміністрація'

export const school = {
  name: 'Сюди: назва школи',
  subtitle: 'Панель адміністрації',
  date: todayLabel(),
}

export const alertBanner = {
  title: 'Сюди: поточна тривога (час початку, скільки учнів відмітились з усіх)',
  text: 'Дані про розташування укриттів видно лише адміністрації.',
  journal: 'Журнал тривог',
}

export type KpiIcon = 'shelter' | 'classes' | 'bell' | 'wifi'

export const kpis: { label: string; value: string; hint: string; icon: KpiIcon; accent?: boolean }[] = [
  { label: 'В укритті зараз', value: '—', hint: 'Сюди: скільки учнів в укритті з усіх і відсоток', icon: 'shelter', accent: true },
  { label: 'Класів', value: '—', hint: 'Сюди: кількість класів і вчителів', icon: 'classes' },
  { label: 'Тривог за тиждень', value: '—', hint: 'Сюди: загальна тривалість за тиждень', icon: 'bell' },
  { label: 'Локальні сервери', value: '—', hint: 'Сюди: скільки серверів онлайн і який офлайн', icon: 'wifi' },
]

export const classes = {
  title: 'Класи в укритті',
  all: 'Усі класи',
  rows: [{ name: 'Сюди: клас', present: 0, total: 0 }],
}

export const users = {
  title: 'Користувачі',
  summary: 'Сюди: кількість учнів і вчителів',
  items: [{ initials: '—', name: 'Сюди: імʼя користувача', role: 'роль і клас' }],
  invite: 'Запросити вчителя',
}

export const alarms = {
  title: 'Журнал тривог',
  export: 'Експорт CSV',
  rows: [
    {
      date: 'Сюди: дата',
      start: 'початок',
      end: 'відбій',
      duration: 'тривалість',
      affected: 'скільки класів зачепило',
      ongoing: false,
    },
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
