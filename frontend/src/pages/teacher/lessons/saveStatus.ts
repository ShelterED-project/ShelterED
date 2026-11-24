import { useSyncExternalStore } from 'react'

// Спільний стан автозбереження редактора: один тихий індикатор «Зберігаю… / Збережено ✓ /
// Не збережено — повторю» замість кнопок «Зберегти» біля кожного поля.

type State = 'saving' | 'failed'

const pending = new Map<string, State>()
let savedOnce = false
let version = 0
const listeners = new Set<() => void>()

function emit() {
  version++
  for (const l of listeners) l()
}

export const saveStatus = {
  start(key: string) {
    pending.set(key, 'saving')
    emit()
  },
  done(key: string) {
    pending.delete(key)
    savedOnce = true
    emit()
  },
  /** Не збережено, але повторимо (мережа). */
  fail(key: string) {
    pending.set(key, 'failed')
    emit()
  },
  /** Більше не відстежуємо (поле зникло чи помилка, яку показує саме поле). */
  clear(key: string) {
    if (pending.delete(key)) emit()
  },
}

/** Обгортка для разових дій (створення, порядок): показує «Зберігаю…», поки йде запит. */
export async function tracked<T>(key: string, action: () => Promise<T>): Promise<T> {
  saveStatus.start(key)
  try {
    const result = await action()
    saveStatus.done(key)
    return result
  } catch (err) {
    saveStatus.clear(key)
    throw err
  }
}

export type OverallSave = 'idle' | 'saving' | 'saved' | 'failed'

function overall(): OverallSave {
  const states = [...pending.values()]
  if (states.includes('failed')) return 'failed'
  if (states.length > 0) return 'saving'
  return savedOnce ? 'saved' : 'idle'
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

export function useOverallSave(): OverallSave {
  useSyncExternalStore(subscribe, () => version)
  return overall()
}

/** Чи є незбережені правки: попереджаємо перед закриттям вкладки. */
export function hasUnsaved(): boolean {
  return pending.size > 0
}
