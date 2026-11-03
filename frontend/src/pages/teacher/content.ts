// TODO: тимчасові моки. Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

// Ім'я й прізвище вчителя беруться з сесії (useCurrentUser). Роль у бекенді без предмета.
export const teacherRole = 'Вчитель'

export const greeting = {
  hello: 'Добрий день',
  subtitle: 'Ліцей №12 · клас 7-Б · вівторок, 14 жовтня',
  mobileSubtitle: '7-Б · вівторок, 14 жовтня',
  classLabel: '7-Б · 27 учнів',
}

export const manualAlarm = { full: 'Оголосити тривогу вручну', short: 'Тривога' }

export const alertBanner = {
  title: 'Повітряна тривога з 10:14 · урок алгебри продовжується офлайн',
  text: 'Учні отримали матеріали автоматично. Локальний сервер у класі працює.',
  action: 'Відкрити перекличку',
}

export type KpiIcon = 'shelter' | 'safe' | 'clock' | 'queue'

export const kpis: { label: string; value: string; hint: string; icon: KpiIcon; accent?: boolean }[] = [
  { label: 'В укритті', value: '22 / 27', hint: 'оновлено о 10:18', icon: 'shelter', accent: true },
  { label: 'В безпеці вдома', value: '3', hint: 'відмітились', icon: 'safe' },
  { label: 'Ще не відмітились', value: '2', hint: 'нагадати можна одним тапом', icon: 'clock' },
  { label: 'Записів у черзі', value: '14', hint: 'синхронізуємо при появі мережі', icon: 'queue' },
]

export type RollCallState = 'shelter' | 'safe' | 'pending'

export const rollCall = {
  title: 'Перекличка 7-Б',
  remind: 'Нагадати',
  note: '«Ще не відмітився» — не привід для паніки: телефон міг просто сісти.',
  rows: [
    { initials: 'ОК', name: 'Оля Ковальчук', state: 'shelter', label: 'в укритті', time: '10:15' },
    { initials: 'МП', name: 'Максим Петренко', state: 'shelter', label: 'в укритті', time: '10:16' },
    { initials: 'ДС', name: 'Дарина Савчук', state: 'safe', label: 'в безпеці', time: '10:15' },
    { initials: 'АБ', name: 'Андрій Бондар', state: 'shelter', label: 'в укритті', time: '10:17' },
    { initials: 'ІЛ', name: 'Іван Литвин', state: 'pending', label: 'ще не відмітився', time: '—' },
    { initials: 'СМ', name: 'Софія Мельник', state: 'shelter', label: 'в укритті', time: '10:18' },
    { initials: 'ТГ', name: 'Тарас Гнатюк', state: 'pending', label: 'ще не відмітився', time: '—' },
  ] as { initials: string; name: string; state: RollCallState; label: string; time: string }[],
}

export const schedule = {
  title: 'Розклад на сьогодні',
  rows: [
    { time: '08:30', subject: 'Геометрія', status: 'Проведено', current: false },
    { time: '09:25', subject: 'Українська література', status: 'Проведено', current: false },
    { time: '10:20', subject: 'Алгебра', status: 'Урок продовжується офлайн', current: true },
    { time: '11:15', subject: 'Історія України', status: 'Пакет готовий', current: false },
    { time: '12:10', subject: 'Англійська мова', status: 'Пакет готовий', current: false },
  ],
}

export const gaps = {
  title: 'Прогалини класу',
  map: 'Мапа класу',
  note: 'Цифра — скільки учнів мають незвідану тему.',
  // share — частка заповнення смужки, у відсотках
  rows: [
    { count: 9, topic: 'Десяткові дроби', share: 83 },
    { count: 4, topic: 'Відсотки', share: 37 },
    { count: 3, topic: 'Пропорції', share: 28 },
  ],
}

export const localServer = {
  title: 'Локальний сервер укриття',
  textBefore: 'Мережа «ShelterED-7B» · 24 пристрої підключено · адреса для учнів: ',
  address: 'shelter.local',
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
