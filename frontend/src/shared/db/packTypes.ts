/** Типи «Рюкзака» за docs/openapi.json (PackOut, PackManifestOut та вкладені схеми). */

export interface MediaManifestItem {
  id: string
  kind: string
  needed_on: string
  sha256: string
  size_bytes: number
  subtitles_id: string | null
  url: string
}

export interface PackManifestItem {
  id: string
  class_id: string
  /** День пакета, YYYY-MM-DD */
  pack_date: string
  version: number
  /** Хеш вмісту: збігається з ETag пакета, за ним вирішуємо, чи докачувати */
  content_hash: string
  size_bytes: number
  built_at: string
}

export interface PackManifest {
  class_id: string
  date_from: string
  date_to: string
  packs: PackManifestItem[]
  media: MediaManifestItem[]
}

export interface ScheduleItem {
  kind: string
  slot_id: string | null
  override_id: string | null
  subject_id: string
  lesson_id: string | null
  /** Місцевий час школи, HH:MM:SS */
  starts_at: string | null
  ends_at: string | null
  starts_at_utc: string | null
  ends_at_utc: string | null
}

export interface PackCard {
  id: string
  module_id: string
  position: number
  kind: string
  /** Форма залежить від kind (наприклад, {text} для текстової картки) */
  body: Record<string, unknown>
  media_asset_id: string | null
}

export interface PackModule {
  id: string
  lesson_id: string
  /** Частина уроку: основна чи укриттєва */
  part: string
  position: number
  title: string
  duration_min: number
  cards: PackCard[]
}

export interface PackOption {
  id: string
  text: string
}

export interface PackQuestion {
  id: string
  kind: string
  prompt: string
  options: PackOption[]
  points: number
  position: number
  /** Лише для тренувальних вправ; для оцінюваних тестів null */
  answer_key: string[] | null
}

export interface PackTest {
  id: string
  title: string
  window_enabled: boolean
  window_hours: number | null
  questions: PackQuestion[]
}

export interface PackLesson {
  id: string
  title: string
  subject_id: string
  main_part: string
  shelter_part: string
  version: number
  modules: PackModule[]
  tests: PackTest[]
}

export interface PackExplanation {
  id: string
  lesson_id: string
  module_id: string | null
  text: string
}

/** Пакет на один день класу. Зберігається в IndexedDB як є. */
export interface Pack {
  id: string
  class_id: string
  pack_date: string
  version: number
  content_hash: string
  built_at: string
  timezone: string
  schedule: ScheduleItem[]
  lessons: PackLesson[]
  explanations: PackExplanation[]
  /** Елементи в схемі не описані; медіа поки не використовуємо */
  media: unknown[]
}
