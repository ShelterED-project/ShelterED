import { store } from '@/app/store'
import { getPendingEvents, markAttempted, OUTBOX_ADDED, removeEvents } from '@/shared/db/outbox'
import { markContact } from './contact'
import { pullChanges } from './syncChanges'
import type { OutboxEvent, WireEvent } from '@/shared/db/types'
import { syncApi } from './syncApi'

/** Ліміт пакета в протоколі v1. */
const BATCH_SIZE = 100
const RETRY_BASE_MS = 5_000
const RETRY_MAX_MS = 5 * 60_000

let running: Promise<void> | null = null
let failures = 0
let retryTimer: ReturnType<typeof setTimeout> | undefined

function toWire(event: OutboxEvent): WireEvent {
  const { client_event_id, type, device_id, occurred_at, payload } = event
  return { client_event_id, type, device_id, occurred_at, payload } as WireEvent
}

function scheduleRetry() {
  failures += 1
  clearTimeout(retryTimer)
  retryTimer = setTimeout(() => void requestSync(), Math.min(RETRY_BASE_MS * 2 ** (failures - 1), RETRY_MAX_MS))
}

/** Відправляє чергу. true — черга порожня (сервер усе підтвердив), false — є що повторити. */
async function drain(): Promise<boolean> {
  // Подію відправляємо лише з токеном її автора: сервер бере користувача з JWT, а не з тіла.
  const userId = store.getState().auth.session?.user.id
  if (!userId) return false

  for (;;) {
    const batch = await getPendingEvents(userId, BATCH_SIZE)
    if (batch.length === 0) {
      failures = 0
      return true
    }

    const response = await store.dispatch(
      syncApi.endpoints.postSyncEvents.initiate(
        { sent_at: new Date().toISOString(), events: batch.map(toWire) },
        { track: false },
      ),
    )
    const ids = batch.map((event) => event.client_event_id)

    // Мережа, 5xx, 401, 501: події лишаються в черзі, повторимо з паузою.
    if ('error' in response) {
      await markContact('events', false)
      await markAttempted(ids)
      scheduleRetry()
      return false
    }

    await markContact('events', true)

    // accepted, duplicate і rejected сервер підтвердив (повторювати rejected безглуздо).
    // Без результатів по жодній події не крутимось у циклі.
    const confirmed = new Set(response.data.results.map((result) => result.client_event_id))
    const done = ids.filter((id) => confirmed.has(id))
    if (done.length === 0) {
      await markAttempted(ids)
      scheduleRetry()
      return false
    }
    await removeEvents(done)
  }
}

/**
 * Відправляє чергу пакетами, а коли вона порожня, підтягує зі стрічки змін результати сервера
 * (оцінки тестів): спершу свої події, потім їхні наслідки. Паралельні виклики ділять один запуск.
 */
export function requestSync(): Promise<void> {
  running ??= drain()
    .then((empty) => (empty ? pullChanges() : undefined))
    .catch(() => scheduleRetry())
    .finally(() => {
      running = null
    })
  return running
}

/**
 * Запускає синхронізацію в моменти, коли вона має сенс: старт, повернення мережі, відкриття застосунку
 * (iOS без Background Sync), нова подія в черзі, вхід іншого користувача.
 */
export function startSync() {
  window.addEventListener('online', () => void requestSync())
  window.addEventListener(OUTBOX_ADDED, () => void requestSync())
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void requestSync()
  })

  let lastUserId = store.getState().auth.session?.user.id
  store.subscribe(() => {
    const userId = store.getState().auth.session?.user.id
    if (userId !== lastUserId) {
      lastUserId = userId
      if (userId) void requestSync()
    }
  })

  void requestSync()
}
