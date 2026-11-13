import { todayLabel } from '@/shared/lib/date'

// Моків немає: там, де мають бути дані з API, стоїть заглушка «Сюди: …» з описом, що саме додати.
// Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).

// Ім'я й прізвище вчителя беруться з сесії (useCurrentUser). Роль у бекенді без предмета.
export const teacherRole = 'Вчитель'

export const greeting = {
  hello: 'Добрий день',
  noClass: 'Клас не призначено',
  loadingClass: 'Завантаження класу…',
}

/** Підпис під привітанням: клас і сьогоднішня дата. */
export function greetingSubtitle(className: string | undefined): string {
  return `${className ?? greeting.noClass} · ${todayLabel()}`
}

export const manualAlarm = {
  full: 'Оголосити тривогу вручну',
  short: 'Тривога',
  end: 'Відбій',
  choose: 'Яку тривогу оголосити для класу?',
  drill: 'Тренувальна',
  real: 'Справжня тривога',
  cancel: 'Скасувати',
  starting: 'Оголошуємо…',
  ending: 'Даємо відбій…',
}

export const alertBanner = {
  loading: 'Завантаження…',
  idleTitle: 'Перекличка не запущена',
  idleText: 'Запустіть її, коли почнеться тривога, або проведіть тренувальну.',
  start: 'Запустити перекличку',
  startDrill: 'Тренувальна',
  activeTitle: 'Перекличка триває',
  drillTitle: 'Тренувальна перекличка триває',
  close: 'Закрити перекличку',
  endAlarm: 'Відбій тривоги',
  endingAlarm: 'Даємо відбій…',
  offline: 'Немає звʼязку, показано останні отримані дані.',
}

export type KpiIcon = 'shelter' | 'safe' | 'clock' | 'queue'

export const kpis: { id: 'in_shelter' | 'safe' | 'no_response' | 'queue'; label: string; icon: KpiIcon; accent?: boolean }[] = [
  { id: 'in_shelter', label: 'В укритті', icon: 'shelter', accent: true },
  { id: 'safe', label: 'В безпеці вдома', icon: 'safe' },
  { id: 'no_response', label: 'Ще не відмітились', icon: 'clock' },
  { id: 'queue', label: 'Записів у черзі', icon: 'queue' },
]

export const kpiHints = {
  noRollCall: 'Перекличка не запущена',
  ofStudents: (total: number) => `з ${total} учнів`,
  queue: 'Чекають синхронізації',
  open: 'Перекличка: усі учні →',
}

export type RollCallState = 'shelter' | 'safe' | 'pending'

export const rollCall = {
  title: 'Перекличка',
  remind: 'Нагадати',
  note: '«Ще не відмітився» — не привід для паніки: телефон міг просто сісти.',
  empty: 'Перекличка не запущена. Запустіть її, щоб побачити учнів класу.',
  loading: 'Завантаження…',
  states: {
    in_shelter: { state: 'shelter', label: 'В укритті' },
    safe: { state: 'safe', label: 'В безпеці' },
    no_response: { state: 'pending', label: 'Ще не відмітився' },
  } as Record<'in_shelter' | 'safe' | 'no_response', { state: RollCallState; label: string }>,
}

export const schedule = {
  title: 'Розклад на сьогодні',
  loading: 'Завантаження…',
  empty: 'Сьогодні уроків немає.',
  offline: 'Немає звʼязку, розклад не завантажено.',
  notAssigned: 'Урок не призначено',
  status: { done: 'Минув', now: 'Зараз', next: 'Далі' },
  week: 'На тиждень',
}

export const schedulePage = {
  title: 'Розклад',
  subtitle: 'Уроки класу на 7 днів від сьогодні',
  today: 'Сьогодні',
  noLessons: 'Уроків немає',
  /** Скільки днів показуємо: як пакети «Рюкзака» (7 днів наперед) */
  days: 7,
}

export const gaps = {
  title: 'Прогалини класу',
  map: 'Мапа класу',
  note: 'Цифра — скільки учнів не склали тест теми, смужка — середня оцінка класу.',
  loading: 'Завантаження…',
  empty: 'Результатів ще немає: учні ще не проходили тести.',
  noGaps: 'Прогалин немає: клас склав тести всіх тем.',
  offline: 'Немає звʼязку, показано останні отримані дані.',
  /** Скільки тем показуємо на огляді; решта на сторінці «Мапа класу». */
  limit: 4,
}

export const classMap = {
  title: 'Мапа класу',
  updated: (time: string) => `Оновлено о ${time}`,
  notComputed: 'Сервер ще не порахував результати класу.',
  loading: 'Завантаження…',
  offline: 'Немає звʼязку, показано останні отримані дані.',
  progress: {
    title: 'Прогрес по уроках',
    empty: 'Уроків у розкладі до сьогодні ще немає.',
    completed: (done: number, total: number) => `Завершили ${done} з ${total}`,
    avgProgress: (pct: number) => `Середній прогрес ${pct}%`,
    tests: (passed: number, scored: number) => `Тест склали ${passed} з ${scored}`,
    noTests: 'Тест ще ніхто не здав',
    avgScore: (score: number) => `Середня оцінка ${Math.round(score)}%`,
  },
  tests: {
    title: 'Тести',
    empty: 'Тестів у класу ще немає.',
    passScore: (pct: number) => `Склав — від ${pct}%`,
    window: (hours: number) => `Вікно ${hours} год`,
    noWindow: 'Без вікна',
    deadline: (time: string) => `до ${time}`,
    suspicious: 'Перевірити час пристрою',
    attempts: (n: number) => `Спроб: ${n}`,
  },
  gaps: {
    title: 'Прогалини по темах',
    empty: 'Результатів тестів ще немає.',
    gap: 'Прогалина',
    ok: 'Засвоєно',
    noScore: 'Оцінок ще немає',
    question: (pct: number, correct: number, answered: number) => `${pct}% правильно (${correct} з ${answered})`,
  },
}

export const testStatus: Record<'passed' | 'not_passed' | 'closing_soon' | 'pending', string> = {
  passed: 'Склав',
  not_passed: 'Не склав',
  closing_soon: 'Вікно закривається',
  pending: 'Ще не здав',
}

export const localServer = {
  title: 'Локальний сервер укриття',
  soon: 'Буде пізніше',
  text: 'Ноутбук вчителя роздаватиме Wi-Fi в укритті: учні працюватимуть без інтернету, а вчитель одним натиском передасть зібране в хмару.',
}

export const qrSync = {
  title: 'QR-синхронізація',
  soon: 'Буде пізніше',
  text: 'Якщо немає ні інтернету, ні локального сервера, учень покаже QR зі своїм прогресом, а вчитель відсканує його телефоном.',
}

export const syncPage = {
  title: 'Синхронізація',
  subtitle: 'Чи готовий клас до роботи без інтернету',
  readiness: {
    title: 'Готовність до укриття',
    hint: 'Учні завантажують ці дні на пристрої, щойно відкривають застосунок з інтернетом.',
    summary: (ready: number, total: number) => `Уроки готові на ${ready} з ${total} навчальних днів`,
    allReady: 'Усі навчальні дні тижня готові.',
    loading: 'Завантаження…',
    offline: 'Немає звʼязку з сервером. Перевірте мережу й натисніть «Оновити».',
    today: 'сьогодні',
    lessons: (n: number, word: string) => `${n} ${word}`,
    state: {
      ready: 'Готово',
      missing: 'Пакета немає',
      unassigned: 'Уроки не призначено',
      free: 'Уроків немає',
    },
    missingHint: 'Перевірте, чи опубліковані уроки цього дня. Пакет збирається за кілька секунд після публікації.',
    built: (size: string, time: string) => `${size} · зібрано ${time}`,
  },
  connection: {
    title: 'Звʼязок',
    internet: 'Інтернет',
    server: 'Сервер',
    updated: 'Оновлено',
    yes: 'Є',
    no: 'Немає',
    ok: 'Відповідає',
    down: 'Не відповідає',
    never: 'Ще не було',
    refresh: 'Оновити',
    refreshing: 'Оновлюємо…',
  },
}
export type NavId = 'overview' | 'rollcall' | 'lessons' | 'schedule' | 'map' | 'sync' | 'settings'

/** Розділи з готовою сторінкою мають маршрут; решта поки без переходу. */
export const navRoutes: Partial<Record<NavId | TabId, string>> = {
  overview: '/teacher',
  rollcall: '/teacher/rollcall',
  lessons: '/teacher/lessons',
  sync: '/teacher/sync',
  schedule: '/teacher/schedule',
  map: '/teacher/map',
}

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
