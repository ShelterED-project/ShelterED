import { pluralUk } from '@/shared/lib/plural'
import type { SkillStatus, StudentLevel } from './testAnalysisApi'

/** Скільки зарахованих спроб потрібно для аналізу (як AI_ANALYSIS_MIN_ATTEMPTS у backend). */
export const MIN_ATTEMPTS = 3

const students = (n: number) => `${n} ${pluralUk(n, ['учень', 'учні', 'учнів'])}`

export const analysisText = {
  run: '🤖 Проаналізувати тест',
  rerun: 'Проаналізувати заново',
  rerunConfirm: 'Новий аналіз замінить цю чернетку разом із правками. Продовжити?',
  needAttempts: (have: number) => `Потрібно щонайменше ${MIN_ATTEMPTS} спроби (зараз ${have})`,
  intro: 'AI розбере відповіді класу: що засвоєно, де типові помилки, і підготує окремі тексти для учнів і батьків.',
  loading: 'Перевіряю, чи є аналіз…',
  processing: 'AI аналізує відповіді класу…',
  processingHint: 'Зазвичай це 10–60 секунд. Можна закрити картку: аналіз продовжиться.',
  loadError: 'Не вдалося завантажити аналіз. Перевірте зʼєднання з сервером.',
  failed: {
    AI_UNAVAILABLE: 'AI-сервіс зараз недоступний.',
    AI_TIMEOUT: 'AI не встиг відповісти.',
    AI_BAD_REQUEST: 'AI-сервіс не прийняв дані тесту.',
    default: 'Аналіз не вдався.',
  } as Record<string, string>,
  startError: {
    NOT_ENOUGH_ATTEMPTS: 'Замало зарахованих спроб для аналізу.',
    TEST_NOT_ANALYZABLE: 'У тесті немає питань з вибором відповіді — AI поки аналізує лише їх.',
    default: 'Не вдалося запустити аналіз. Спробуйте ще раз.',
  } as Record<string, string>,
  retry: 'Спробувати ще раз',

  draftBadge: 'Чернетка — бачите лише ви',
  publishedBadge: (when: string) => `Опубліковано ${when}`,
  templateNote: 'AI-модель не відповіла, тому тексти зібрано за шаблоном.',
  basedOn: (n: number, when: string) => `За ${n} ${pluralUk(n, ['спробою', 'спробами', 'спробами'])} · ${when}`,

  kpiAverage: 'Середній бал',
  kpiPassed: 'Склали',
  kpiSupport: 'Потребують підтримки',
  of: (a: number, b: number) => `${a} з ${b}`,

  overviewTitle: 'Висновок для вчителя',
  recommendationsTitle: 'Що зробити на наступному уроці',
  skillsTitle: 'Вміння',
  skillStatus: { ok: 'засвоєно', attention: 'варто повторити', critical: 'прогалина' } as Record<SkillStatus, string>,
  misconceptionsTitle: 'Типові помилки',
  misconceptionWho: (n: number, pct: number) => `${students(n)} · ${Math.round(pct)}% класу`,

  studentsTitle: 'Учні',
  studentsHint: 'Відкрийте учня, щоб переглянути й за потреби виправити тексти перед публікацією.',
  level: { strong: 'добре', ok: 'норма', needs_support: 'потребує підтримки' } as Record<StudentLevel, string>,
  forTeacher: 'Для вас',
  forStudent: 'Учню',
  forParent: 'Батькам',
  edited: 'виправлено вами',
  edit: 'Редагувати',
  save: 'Зберегти',
  cancel: 'Скасувати',
  resetToAi: 'Повернути текст AI',
  saveError: 'Не вдалося зберегти. Спробуйте ще раз.',

  publish: 'Опублікувати учням і батькам',
  publishConfirm: 'Учні й батьки побачать свої тексти. Після публікації правки вже неможливі.',
  confirm: 'Так, опублікувати',
  publishedNote: 'Учні бачать свій текст на сторінці «Я», батьки — у «Прогресі».',
  publishError: 'Не вдалося опублікувати. Спробуйте ще раз.',
  unknownStudent: 'Учень',
}

export const feedbackText = {
  title: 'Розбір тестів від вчителя',
  empty: 'Вчитель ще не надсилав розбору тестів.',
  emptyParent: 'Вчитель ще не надсилав розбору тестів дитини.',
  offline: 'Не вдалося завантажити розбір. Перевірте зʼєднання.',
  score: (correct: number, total: number) => `${correct} з ${total}`,
}
