import { todayLabel } from '@/shared/lib/date'

// Моків немає: там, де мають бути дані з API, стоїть заглушка «Сюди: …» з описом, що саме додати.
// Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

// Ім'я й прізвище вчителя беруться з сесії (useCurrentUser). Роль у бекенді без предмета.
export const teacherRole = 'Вчитель'

export const greeting = {
  hello: 'Добрий день',
  subtitle: `Сюди: школа · клас · ${todayLabel()}`,
  mobileSubtitle: `Сюди: клас · ${todayLabel()}`,
  classLabel: 'Сюди: клас · кількість учнів',
}

export const manualAlarm = { full: 'Оголосити тривогу вручну', short: 'Тривога' }

export const alertBanner = {
  title: 'Сюди: поточна тривога (час початку, що з уроком)',
  text: 'Сюди: чи отримали учні матеріали і чи працює локальний сервер',
  action: 'Відкрити перекличку',
}

export type KpiIcon = 'shelter' | 'safe' | 'clock' | 'queue'

export const kpis: { label: string; value: string; hint: string; icon: KpiIcon; accent?: boolean }[] = [
  { label: 'В укритті', value: '—', hint: 'Сюди: скільки в укритті з усіх і час оновлення', icon: 'shelter', accent: true },
  { label: 'В безпеці вдома', value: '—', hint: 'Сюди: скільки відмітились вдома', icon: 'safe' },
  { label: 'Ще не відмітились', value: '—', hint: 'Сюди: скільки учнів без відмітки', icon: 'clock' },
  { label: 'Записів у черзі', value: '—', hint: 'Сюди: скільки подій чекає синхронізації', icon: 'queue' },
]

export type RollCallState = 'shelter' | 'safe' | 'pending'

export const rollCall = {
  title: 'Перекличка',
  remind: 'Нагадати',
  note: '«Ще не відмітився» — не привід для паніки: телефон міг просто сісти.',
  rows: [{ initials: '—', name: 'Сюди: імʼя учня', state: 'pending', label: 'статус відмітки', time: '—' }] as {
    initials: string
    name: string
    state: RollCallState
    label: string
    time: string
  }[],
}

export const schedule = {
  title: 'Розклад на сьогодні',
  rows: [{ time: '—', subject: 'Сюди: предмет', status: 'статус уроку', current: false }],
}

export const gaps = {
  title: 'Прогалини класу',
  map: 'Мапа класу',
  note: 'Цифра — скільки учнів мають незвідану тему.',
  // share — частка заповнення смужки, у відсотках. Сюди: теми з прогалинами.
  rows: [{ count: 0, topic: 'Сюди: тема', share: 0 }],
}

export const localServer = {
  title: 'Локальний сервер укриття',
  textBefore: 'Сюди: назва мережі, кількість підключених пристроїв, адреса для учнів: ',
  address: '—',
  sync: 'Синхронізувати з хмарою',
}

export type NavId = 'overview' | 'rollcall' | 'lessons' | 'schedule' | 'map' | 'sync' | 'settings'

export const sidebarNav: { id: NavId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'rollcall', label: 'Перекличка' },
  { id: 'lessons', label: 'Уроки' },
  { id: 'schedule', label: 'Розклад' },
  { id: 'map', label: 'Мапа класу' },
  { id: 'sync', label: 'Синхронізація' },
  { id: 'settings', label: 'Налаштування' },
]

export type TabId = 'overview' | 'rollcall' | 'lessons' | 'more'

export const mobileTabs: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'rollcall', label: 'Перекличка' },
  { id: 'lessons', label: 'Уроки' },
  { id: 'more', label: 'Ще' },
]
