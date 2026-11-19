import type { StudentTestStatus } from '@/features/student/studentApi'
import { todayLabel } from '@/shared/lib/date'
import { pluralUk } from '@/shared/lib/plural'

// Ім'я батьків беремо з сесії (useCurrentUser), дітей — з GET /parent/children.
export const parentRole = 'Батьки'

export const greeting = { hello: 'Вітаємо', date: todayLabel({ capitalize: true }) }

export const childPicker = { label: 'Дитина' }

export const loading = 'Завантажуємо дані…'
export const offline = 'Немає звʼязку з сервером. Показано останні збережені дані.'

export const safetyStatus = {
  alert: (time: string, drill: boolean) => (drill ? `Тренувальна тривога з ${time}` : `Повітряна тривога з ${time}`),
  noAlert: 'Тривоги зараз немає',
  inShelter: (name: string) => `${name} в укритті`,
  safe: (name: string) => `${name} в безпеці`,
  noMark: (name: string) => `${name}: ще немає відмітки в перекличці`,
  noRollCall: 'Вчитель ще не почав перекличку',
  calm: 'Усе спокійно',
  markedAt: (time: string) => `Відмітка о ${time}`,
  noMarkText: 'Щойно дитина натисне «Я в укритті» чи «Я в безпеці», статус зʼявиться тут.',
  calmText: 'Коли почнеться тривога, тут буде видно, чи дитина в укритті.',
  dataTime: (time: string) => `Дані на ${time}`,
  dataOffline: 'Без звʼязку: останні збережені дані',
  note: 'Оновлюється саме. Якщо в укритті немає звʼязку, дані підтягнуться, щойно він зʼявиться.',
}

export const kpis = {
  lessons: {
    label: 'Уроків за тиждень',
    hint: (started: number) => `розпочато ${started} ${pluralUk(started, ['урок', 'уроки', 'уроків'])}`,
  },
  time: {
    label: 'Час навчання',
    value: (minutes: number) => `${minutes} хв`,
    hint: (total: number) => `за весь час ${total} хв`,
  },
  score: {
    label: 'Середній бал тестів',
    hint: (n: number) => (n === 0 ? 'тестів ще немає' : `за ${n} ${pluralUk(n, ['тест', 'тести', 'тестів'])}`),
  },
  gaps: {
    label: 'Що повторити',
    hint: (n: number) => (n === 0 ? 'прогалин немає' : pluralUk(n, ['предмет', 'предмети', 'предметів'])),
  },
}

export const week = {
  title: 'Навчання за тиждень',
  range: 'останні 7 днів',
  minutes: (day: string, minutes: number) => `${day}: ${minutes} хв`,
  empty: 'За останній тиждень уроків ще не було.',
}

export const homework = {
  title: 'Що повторити вдома',
  all: 'Усі',
  gap: (subject: string) => ({ title: subject, note: 'тест не складено або вікно тесту спливло' }),
  test: (title: string, status: string) => ({ title, note: status }),
  moleSays: (n: number) =>
    n === 0
      ? 'Прогалин немає! Можна просто спитати, що було найцікавішим.'
      : 'Почніть з першої теми у списку: 10 хвилин разом краще, ніж година наодинці.',
}

export const testStatus: Record<StudentTestStatus, string> = {
  passed: 'складено',
  not_passed: 'не складено',
  closing_soon: 'скоро закриється',
  pending: 'ще не пройдено',
}

export const linkChild = {
  title: 'Додати дитину',
  text: 'Код дає класний керівник або адміністрація школи. Він діє 7 днів.',
  emptyTitle: 'Привʼяжіть дитину',
  emptyText: 'Щоб бачити статус безпеки й прогрес, введіть код, який дав класний керівник.',
  placeholder: 'Код від вчителя',
  required: 'Введіть код від вчителя',
  submit: 'Додати',
  submitting: 'Перевіряємо…',
  added: (name: string) => `Дитину ${name} додано.`,
}

export const rollCallLog = {
  title: 'Журнал переклички',
  soon: 'Буде пізніше',
  text: 'Історія відміток за минулі тривоги. Поки видно лише поточну перекличку вгорі сторінки.',
}

export const teacherMessage = {
  title: 'Повідомлення від вчителя',
  soon: 'Буде пізніше',
  text: 'Чат із класним керівником зʼявиться в наступній версії.',
}

export const visibility = {
  title: 'Що ви бачите',
  items: [
    { text: 'Статус переклички дитини', visible: true },
    { text: 'Прогрес і пропущені теми', visible: true },
    { text: 'Настрій за тиждень словами, без окремих відповідей', visible: true },
    { text: 'Геолокацію — ми її не збираємо', visible: false },
    { text: 'Дані інших учнів класу', visible: false },
  ],
}

export const progressPage = {
  title: 'Прогрес',
  subtitle: (name: string) => `Уроки, тести й теми: ${name}`,
  lessons: {
    title: 'Уроки',
    empty: 'Уроків ще немає.',
    modules: (done: number, total: number) => `${done} з ${total} ${pluralUk(total, ['модуль', 'модулі', 'модулів'])}`,
    minutes: (n: number) => `${n} хв`,
  },
  tests: {
    title: 'Тести',
    empty: 'Тестів ще немає.',
    score: (score: number) => `${Math.round(score)}%`,
    attempts: (n: number) => `${n} ${pluralUk(n, ['спроба', 'спроби', 'спроб'])}`,
    deadline: (date: string) => `до ${date}`,
  },
  map: {
    title: 'Мапа знань',
    empty: 'Предметів ще немає.',
    lessons: (done: number, total: number) => `${done} з ${total} уроків`,
    gap: 'варто повторити',
    score: (score: number) => `середній бал ${Math.round(score)}%`,
  },
  wellbeing: {
    title: 'Як почувається дитина цього тижня',
    week: (from: string, to: string) => `${from} – ${to}`,
    offline: 'Зведення видно лише з інтернетом: ми не зберігаємо його на пристрої.',
    tipsTitle: 'Що можна зробити',
    about:
      'Це не тест і не оцінка стану: дитина лише обирає картинку погоди, коли хоче. Окремих відповідей ви не бачите.',
  },
}

export const parentSettings = {
  childrenTitle: 'Мої діти',
  noChildren: 'Дітей ще не додано.',
}

export type NavId = 'overview' | 'progress' | 'messages' | 'notifications' | 'settings'
export type TabId = 'overview' | 'progress' | 'chat' | 'more'

export const navRoutes: Partial<Record<NavId | TabId, string>> = {
  overview: '/parent',
  progress: '/parent/progress',
  settings: '/parent/settings',
  more: '/parent/settings',
}

export const sidebarNav: { id: NavId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'progress', label: 'Прогрес' },
  { id: 'messages', label: 'Повідомлення' },
  { id: 'notifications', label: 'Сповіщення' },
  { id: 'settings', label: 'Налаштування' },
]

export const mobileTabs: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'progress', label: 'Прогрес' },
  { id: 'chat', label: 'Чат' },
  { id: 'more', label: 'Налаштування' },
]
