import { pluralUk } from '@/shared/lib/plural'

export const settingsTitle = 'Налаштування'

export const profile = {
  title: 'Профіль',
  name: 'Імʼя',
  role: 'Роль',
  roles: { student: 'Учень', teacher: 'Вчитель', parent: 'Батьки', admin: 'Адміністрація школи' },
  note: 'Якщо в імені помилка, напишіть адміністрації школи.',
}

export const device = {
  title: 'Цей пристрій',
  internet: 'Інтернет',
  online: 'є',
  offline: 'немає',
  lastSync: 'Остання синхронізація',
  never: 'ще не було',
  packs: 'Уроки на пристрої',
  packsNone: 'не завантажені',
  packsDays: (n: number) => `на ${n} ${pluralUk(n, ['день', 'дні', 'днів'])}`,
  app: 'Без мережі',
  appReady: 'відкриється',
  appNotReady: 'ще ні',
  queue: 'Не відправлено',
  queueValue: (n: number) => (n === 0 ? 'нічого' : `${n} ${pluralUk(n, ['запис', 'записи', 'записів'])}`),
  used: 'Займає',
  usedValue: (used: string, quota: string | null) => (quota ? `${used} з ${quota}` : used),
  sync: 'Синхронізувати зараз',
  syncing: 'Синхронізуємо…',
  persist: {
    title: 'Захист даних',
    on: 'Браузер не стиратиме уроки й невідправлені відповіді, навіть коли бракує місця.',
    off: 'Коли на телефоні бракує місця, браузер може стерти збережені уроки й відповіді, які ще не відправлено.',
    button: 'Захистити дані',
    denied: 'Браузер не дозволив. Встановіть застосунок на головний екран і спробуйте ще раз.',
  },
}

export const signOut = {
  title: 'Вихід',
  text: 'Збережений вхід на цьому пристрої видаляється. Щоб повернутися, увійдіть знову.',
  pending: (n: number) =>
    `${n} ${pluralUk(n, ['запис ще не відправлено', 'записи ще не відправлено', 'записів ще не відправлено'])}. Вони лишаться на пристрої й відправляться, коли ви знову увійдете.`,
  button: 'Вийти з акаунта',
}

/** Байти як «12,3 МБ». */
export function bytesLabel(bytes: number): string {
  const units = ['Б', 'КБ', 'МБ', 'ГБ']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return `${value.toLocaleString('uk-UA', { maximumFractionDigits: unit === 0 ? 0 : 1 })} ${units[unit]}`
}
