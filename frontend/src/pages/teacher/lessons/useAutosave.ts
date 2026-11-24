import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage, isNetworkError } from '@/features/teacher/lessonEditorApi'
import { db } from '@/shared/db/db'
import { saveStatus } from './saveStatus'

/** Пауза після останнього натискання, після якої зберігаємо. */
export const AUTOSAVE_DELAY = 800
/** Через скільки повторюємо, якщо мережі немає (і одразу, щойно вона зʼявилась). */
const RETRY_DELAY = 5000

export type FieldSave = 'idle' | 'saving' | 'saved' | 'retry' | 'error' | 'invalid'

/** Порівняння без різниці в пробілах на краях і між null та порожнім рядком (так нормалізує сервер). */
function normalize(value: unknown): unknown {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') return value.trim()
  if (Array.isArray(value)) return value.map(normalize)
  if (typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => [k, normalize(v)]),
    )
  }
  return value
}

export function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(normalize(a)) === JSON.stringify(normalize(b))
}

interface Options<T> {
  /** Ключ чернетки в IndexedDB, унікальний для поля */
  draftKey: string
  /** Значення з сервера */
  server: T
  /** Зберегти на сервері; помилка — виняток */
  save: (value: T) => Promise<unknown>
  delay?: number
  disabled?: boolean
  /** Неповне значення (напр. питання без правильної відповіді) не відправляємо */
  isValid?: (value: T) => boolean
  /** Чи значення однакові для сервера (за замовчуванням sameValue) */
  same?: (a: T, b: T) => boolean
}

/**
 * Автозбереження поля: зміни йдуть на сервер через паузу після введення. Незбережене лежить
 * у IndexedDB (обрив мережі чи закрита вкладка не губить текст) і повторюється, щойно
 * зʼявилась мережа. Значення з сервера підхоплюємо, лише коли локальних правок немає.
 */
export function useAutosave<T>({
  draftKey,
  server,
  save,
  delay = AUTOSAVE_DELAY,
  disabled = false,
  isValid,
  same = sameValue,
}: Options<T>) {
  const [value, setValue] = useState<T>(server)
  const [status, setStatus] = useState<FieldSave>('idle')
  const [error, setError] = useState<string | null>(null)

  const valueRef = useRef(value)
  const savedRef = useRef<T>(server)
  const dirtyRef = useRef(false)
  // Те саме, що dirtyRef, але для рендера (refs під час рендера не читаємо).
  const [dirty, setDirty] = useState(false)
  const markDirty = useCallback((next: boolean) => {
    dirtyRef.current = next
    setDirty(next)
  }, [])
  const busyRef = useRef(false)
  const timerRef = useRef<number | undefined>(undefined)
  const saveRef = useRef(save)
  const validRef = useRef(isValid)
  const sameRef = useRef(same)
  const runRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    saveRef.current = save
    validRef.current = isValid
    sameRef.current = same
  })

  const schedule = useCallback((ms: number) => {
    window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => void runRef.current(), ms)
  }, [])

  useEffect(() => {
    runRef.current = async () => {
      window.clearTimeout(timerRef.current)
      if (!dirtyRef.current || disabled) return
      if (busyRef.current) return schedule(delay)
      const current = valueRef.current
      if (validRef.current && !validRef.current(current)) {
        setStatus('invalid')
        saveStatus.clear(draftKey)
        return
      }
      busyRef.current = true
      setStatus('saving')
      setError(null)
      saveStatus.start(draftKey)
      try {
        await saveRef.current(current)
        savedRef.current = current
        markDirty(!sameRef.current(valueRef.current, current))
        if (dirtyRef.current) {
          schedule(delay)
        } else {
          await db.editorDrafts.delete(draftKey).catch(() => undefined)
          setStatus('saved')
          saveStatus.done(draftKey)
        }
      } catch (err) {
        if (isNetworkError(err)) {
          setStatus('retry')
          saveStatus.fail(draftKey)
          schedule(RETRY_DELAY)
        } else {
          setStatus('error')
          setError(errorMessage(err))
          saveStatus.clear(draftKey)
        }
      } finally {
        busyRef.current = false
      }
    }
  })

  // Нове значення з сервера (напр. після копіювання чи іншої вкладки): беремо, якщо не редагуємо.
  const serverKey = JSON.stringify(normalize(server))
  const [lastServerKey, setLastServerKey] = useState(serverKey)
  if (serverKey !== lastServerKey) {
    setLastServerKey(serverKey)
    if (!dirty && !same(server, value)) setValue(server)
  }
  useEffect(() => {
    if (!dirtyRef.current) {
      savedRef.current = server
      valueRef.current = value
    }
  })

  // Чернетка, що лишилась з минулого разу (не дійшла до сервера): відновлюємо й відправляємо.
  useEffect(() => {
    if (disabled) return
    let alive = true
    void db.editorDrafts
      .get(draftKey)
      .then((draft) => {
        if (!alive || !draft || sameRef.current(draft.value as T, savedRef.current)) return
        valueRef.current = draft.value as T
        markDirty(true)
        setValue(draft.value as T)
        schedule(0)
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [draftKey, disabled, schedule, markDirty])

  useEffect(() => {
    const online = () => {
      if (dirtyRef.current) void runRef.current()
    }
    window.addEventListener('online', online)
    return () => {
      window.removeEventListener('online', online)
      window.clearTimeout(timerRef.current)
      // Поле зникло з екрана з незбереженими правками: відправляємо одразу (чернетка лишається
      // в IndexedDB до підтвердження).
      if (dirtyRef.current && !busyRef.current) void runRef.current()
      else saveStatus.clear(draftKey)
    }
  }, [draftKey])

  const set = useCallback(
    (next: T) => {
      valueRef.current = next
      setValue(next)
      markDirty(!sameRef.current(next, savedRef.current))
      if (dirtyRef.current) {
        void db.editorDrafts.put({ key: draftKey, value: next, updatedAt: Date.now() }).catch(() => undefined)
        setStatus((s) => (s === 'invalid' || s === 'error' ? 'idle' : s))
        schedule(delay)
      } else {
        void db.editorDrafts.delete(draftKey).catch(() => undefined)
        window.clearTimeout(timerRef.current)
      }
    },
    [draftKey, delay, schedule, markDirty],
  )

  /** Зберегти одразу (напр. при виході з поля). */
  const flush = useCallback(() => void runRef.current(), [])

  return { value, set, flush, status, error }
}
