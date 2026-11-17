import type { ListedRole } from '@/features/admin/adminApi'
import { todayLabel } from '@/shared/lib/date'
import { pluralUk } from '@/shared/lib/plural'

// Ім'я адміна беремо з сесії (useCurrentUser); посади й назви школи в API немає.
export const adminRole = 'Адміністрація'

export const school = {
  name: 'Моя школа',
  subtitle: 'Панель адміністрації',
  date: todayLabel(),
}

export const loading = 'Завантажуємо дані школи…'
export const offline = 'Немає звʼязку з сервером. Показано останні отримані дані.'

export const minutesLabel = (n: number) => (n < 60 ? `${n} хв` : `${Math.floor(n / 60)} год ${n % 60} хв`)

export const alertBanner = {
  active: (time: string, drill: boolean) => (drill ? `Тренувальна тривога з ${time}` : `Повітряна тривога з ${time}`),
  marked: (marked: number, total: number) =>
    total === 0 ? 'Перекличку в класах ще не почато.' : `Відмітились ${marked} з ${total} учнів.`,
  calm: 'Тривоги зараз немає',
  calmText: 'Коли почнеться тривога, тут буде видно, скільки учнів уже в укритті.',
  journal: 'Журнал тривог',
}

export const kpis = {
  shelter: {
    label: 'В укритті зараз',
    hint: (total: number, safe: number) => (total === 0 ? 'переклички немає' : `з ${total} учнів, ще ${safe} в безпеці`),
  },
  classes: {
    label: 'Класів',
    hint: (teachers: number) => `${teachers} ${pluralUk(teachers, ['вчитель', 'вчителі', 'вчителів'])}`,
  },
  alarms: {
    label: 'Тривог за тиждень',
    hint: (minutes: number) => (minutes === 0 ? 'тривог не було' : `разом ${minutesLabel(minutes)}`),
  },
  servers: { label: 'Локальні сервери', value: '—', hint: 'Моніторинг серверів зʼявиться пізніше' },
}

export const classes = {
  title: 'Класи в укритті',
  all: 'Усі класи',
  empty: 'Класів ще немає.',
  noRollCall: 'переклички немає',
  allMarked: 'усі відмітились',
  missing: (n: number) => `${n} не відмітились`,
}

export const users = {
  title: 'Вчителі',
  summary: (n: number) => `${n} ${pluralUk(n, ['вчитель', 'вчителі', 'вчителів'])}`,
  empty: 'Вчителів ще немає.',
  all: 'Усі користувачі',
  invite: 'Запросити вчителя',
}

export const roleLabels: Record<ListedRole, string> = {
  teacher: 'Вчитель',
  admin: 'Адміністрація',
  student: 'Учень',
}

export const alarms = {
  title: 'Журнал тривог',
  recent: 'Останні тривоги',
  all: 'Увесь журнал',
  export: 'Експорт CSV',
  empty: 'За цей період тривог не було.',
  ongoing: 'триває',
  drill: 'тренувальна',
  manual: 'ручна',
  fromApi: 'з API тривог',
  wholeSchool: 'уся школа',
  columns: { date: 'Дата', start: 'Початок', end: 'Відбій', duration: 'Тривалість', scope: 'Де', kind: 'Тип' },
  range: { from: 'Від', to: 'До', apply: 'Показати' },
  csvName: (from: string, to: string) => `alerts_${from}_${to}.csv`,
}

export const classesPage = {
  title: 'Класи',
  subtitle: 'Створення класів, коди для учнів, вчителі й учні',
  add: 'Новий клас',
  form: {
    name: 'Назва',
    namePlaceholder: '5-А',
    grade: 'Рік навчання',
    year: 'Навчальний рік',
    yearHint: 'У форматі 2026/2027',
    save: 'Зберегти',
    create: 'Створити',
    cancel: 'Скасувати',
    nameRequired: 'Вкажіть назву класу',
    yearInvalid: 'Формат: 2026/2027',
  },
  joinCode: 'Код для учнів',
  joinCodeUntil: (date: string) => `діє до ${date}`,
  newCode: 'Новий код',
  confirmNewCode: 'Старий код перестане діяти одразу. Видати новий?',
  teachers: 'Вчителі класу',
  noTeachers: 'Вчителя не призначено',
  addTeacher: 'Призначити вчителя',
  removeTeacher: (name: string) => `Зняти ${name} з класу`,
  students: 'Учні',
  showStudents: 'Показати учнів',
  hideStudents: 'Сховати учнів',
  edit: 'Змінити',
  remove: 'Видалити',
  confirmRemove: (name: string) => `Видалити клас ${name}? Видалити можна лише клас без учнів.`,
  grade: (grade: number, year: string) => `${grade} клас · ${year}`,
}

export const usersPage = {
  title: 'Користувачі',
  subtitle: 'Вчителі, адміністрація й учні школи',
  add: 'Додати користувача',
  search: 'Пошук за імʼям',
  filterAll: 'Усі',
  empty: 'Нікого не знайдено.',
  count: (n: number) => `${n} ${pluralUk(n, ['користувач', 'користувачі', 'користувачів'])}`,
  parentsNote: 'Батьків у списку немає: вони привʼязуються до дітей кодом від вчителя чи адміністрації.',
}

export type NavId = 'overview' | 'classes' | 'users' | 'alarms' | 'servers' | 'settings'
export type TabId = 'overview' | 'classes' | 'alarms' | 'more'

export const navRoutes: Partial<Record<NavId | TabId, string>> = {
  overview: '/admin',
  classes: '/admin/classes',
  users: '/admin/users',
  alarms: '/admin/alarms',
  more: '/admin/users',
}

export const sidebarNav: { id: NavId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'classes', label: 'Класи' },
  { id: 'users', label: 'Користувачі' },
  { id: 'alarms', label: 'Журнал тривог' },
  { id: 'servers', label: 'Локальні сервери' },
  { id: 'settings', label: 'Налаштування школи' },
]

export const mobileTabs: { id: TabId; label: string }[] = [
  { id: 'overview', label: 'Огляд' },
  { id: 'classes', label: 'Класи' },
  { id: 'alarms', label: 'Тривоги' },
  { id: 'more', label: 'Люди' },
]
