import { todayLabel } from '@/shared/lib/date'
import { pluralUk } from '@/shared/lib/plural'

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
  // Уроки сьогодні були, але за розкладом усі вже минули: їх усе одно можна пройти з пакета.
  allDone: 'Уроки на сьогодні завершено',
  allDoneTitle: 'Повтори або пройди пропущене',
  allDoneText: (count: number, word: string) => `Сьогодні ${count} ${word}, усі збережено на пристрої.`,
  toLessons: 'До уроків',
  open: 'Відкрити урок',
  breathe: 'Подихати',
}

export const route = {
  title: 'Мій маршрут на сьогодні',
  range: (done: number, total: number) => `Пройдено ${done} з ${total}`,
  loading: 'Шукаю твій маршрут…',
  moleNoPack: 'Підключись до мережі один раз, і я збережу сьогоднішні уроки.',
  statusLabel: { done: 'Пройдено', current: 'Зараз', todo: 'Далі' },
  moleStart: (lesson: string) => `Далі урок «${lesson}».`,
  moleDone: 'Усе, що є, пройдено. Молодець!',
  moleEmpty: 'Сьогодні уроків немає. Відпочивай!',
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

export const calm = { title: 'Хвилинка спокою', text: 'Вдих 4 · пауза 4 · видих 6 · 2 хв' }

export const todayLessons = {
  title: 'Мої уроки',
  backpackReady: 'Рюкзак на сьогодні зібрано',
  backpackMissing: 'Рюкзак на сьогодні ще не зібрано',
  backpackText: (lessons: number) =>
    `${lessons} ${pluralUk(lessons, ['урок', 'уроки', 'уроків'])} · усе працює без інтернету`,
  backpackMissingText: 'Підключись до мережі один раз, і уроки збережуться на пристрої.',
  updated: (time: string) => `оновлено ${time}`,
  allSubjects: 'Усі предмети',
  otherSubject: 'Інше',
  view: { days: 'Дні', subjects: 'Предмети' },
  today: (weekday: string) => `Сьогодні · ${weekday}`,
  tomorrow: (weekday: string) => `Завтра · ${weekday}`,
  empty: 'На сьогодні уроків немає.',
  modules: (n: number) => `${n} ${pluralUk(n, ['модуль', 'модулі', 'модулів'])}`,
  minutes: (n: number) => `${n} хв`,
  withTest: 'тест',
  withWindow: (hours: number) => `тест з вікном ${hours} год`,
  now: 'зараз',
  done: 'Пройдено',
  offline: 'офлайн ✓',
  inBackpack: 'у Рюкзаку',
  windowTests: {
    title: 'Тести з вікном',
    empty: 'Відкритих тестів немає.',
    note: 'Тест можна пройти будь-коли у вікні, навіть в укритті.',
    until: (when: string) => `до ${when}`,
    hoursLeft: (n: number) => `ще ${n} год`,
    daysLeft: (n: number) => `ще ${n} ${pluralUk(n, ['день', 'дні', 'днів'])}`,
  },
  gaps: {
    title: 'Пропущені теми',
    lessons: (done: number, total: number) => `${done} з ${total} уроків пройдено`,
    toMap: 'На мапу',
  },
}

export type NavId = 'route' | 'lessons' | 'calm' | 'me' | 'settings'

/** Розділи з готовою сторінкою мають маршрут; решта поки без переходу. */
export const navRoutes: Partial<Record<NavId, string>> = {
  route: '/student',
  lessons: '/student/lessons',
  me: '/student/me',
  calm: '/student/calm',
  settings: '/student/settings',
}

export const calmPage = {
  title: 'Спокій',
  subtitle: 'Хвилинка для себе. Тут нічого не оцінюють.',
  offlineNoTexts: 'Щоб відповісти «Як ти зараз?», підключись до мережі один раз. Подихати можна й зараз.',
  answeredToday: 'Сьогоднішня відповідь уже є. Якщо настрій змінився, можна обрати іншу картинку.',
  change: 'Змінити відповідь',
  call: 'Подзвонити',
  breathing: {
    title: 'Хвилинка спокою',
    text: 'Вдих 4 · пауза 4 · видих 6 · 2 хв',
    hint: 'Сядь зручно. Дихай повільно разом з кругом. Можна з заплющеними очима.',
    start: 'Почати',
    stop: 'Зупинити',
    again: 'Ще раз',
    done: 'Молодець. Можна повторити, скільки захочеш.',
    phases: { inhale: 'Вдихни', hold: 'Затримай', exhale: 'Видихни' },
    left: (seconds: number) => `ще ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`,
  },
  history: { empty: 'Тут зʼявляться твої картинки, коли ти відповіси кілька днів.' },
}

export const mePage = {
  title: 'Я',
  updated: (time: string) => `Оновлено ${time}`,
  notComputed: 'Сервер ще не порахував твій прогрес. Пройди урок, і він зʼявиться.',
  loading: 'Завантаження…',
  offline: 'Немає звʼязку, показано останні збережені дані.',
  offlineEmpty: 'Немає звʼязку. Прогрес зʼявиться, щойно підключишся до мережі.',
  study: {
    title: 'Час навчання',
    week: 'За 7 днів',
    total: 'Усього',
    minutes: (n: number) => `${n} хв`,
    hint: 'Рахуються завершені модулі.',
  },
  tests: {
    title: 'Мої тести',
    empty: 'Тестів поки немає.',
    status: {
      closing_soon: 'Скоро закінчиться вікно',
      pending: 'Ще не здано',
      not_passed: 'Не складено',
      passed: 'Складено',
    },
    deadline: (when: string) => `здати до ${when}`,
    noWindow: 'без обмеження часу',
    attempts: (n: number) => `спроб: ${n}`,
  },
  lessons: {
    title: 'Мої уроки',
    empty: 'Уроків поки немає.',
    modules: (done: number, total: number) => `модулів ${done} з ${total}`,
    done: 'Пройдено',
  },
}

export const studentSettings = {
  pinNote: 'Імʼя чи PIN змінює вчитель. Якщо забув PIN, попроси вчителя скинути його: при наступному вході придумаєш новий.',
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

export const lessonPage = {
  backpack: 'Рюкзак ✓',
  online: 'Онлайн',
  offline: 'Офлайн',
  help: 'Безпека',
  progress: (module: number, card: number, total: number) => `Модуль ${module} · картка ${card} з ${total}`,
  minutes: (n: number) => `≈ ${n} хв`,
  cardEyebrow: (card: number, kind: string) => `Картка ${card} · ${kind}`,
  kinds: { text: 'Текст', image: 'Малюнок', video: 'Відео' } as Record<string, string>,
  // Медіа «Рюкзака» на пристрій ще не завантажуються: показуємо підпис і пояснення.
  mediaPending: 'Цей матеріал відкриється, коли медіа уроку збережеться на пристрої.',
  nextCard: (card: number) => `Далі · картка ${card}`,
  nextStep: 'Далі',
  back: 'Назад',
  next: 'Далі',
  outline: { shelter: 'Укриттєва частина', main: 'Основна частина' },
  module: (n: number, title: string) => `Модуль ${n} · ${title}`,
  test: (questions: number) => `Тест · ${questions} ${pluralUk(questions, ['питання', 'питання', 'питань'])}`,
  moduleMinutes: (n: number) => `${n} хв`,
  testWindow: (hours: number) => `вікно ${hours} год`,
  testPractice: 'тренувальний',
  queue: (n: number) => (n === 0 ? 'Черга порожня' : `${n} ${pluralUk(n, ['запис', 'записи', 'записів'])} в черзі`),
  queueSent: 'усе відправлено',
  queueWaiting: 'відправимо, щойно зʼявиться звʼязок',
  queueNote: 'Пройдені модулі збережено на пристрої.',
}
