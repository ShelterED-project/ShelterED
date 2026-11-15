import { db } from '@/shared/db/db'

/** Канали обміну з сервером: відправка подій і завантаження пакетів уроків. */
export type ContactChannel = 'events' | 'packs'

/** Ключі в таблиці meta: час останнього вдалого й невдалого звернення до сервера (ISO). */
export const contactKey = (channel: ContactChannel, ok: boolean) => `contact:${channel}:${ok ? 'ok' : 'error'}`

/**
 * Запамʼятовує, чи відповів сервер. Лише для екрана «Звʼязок»: на синхронізацію не впливає,
 * тож помилку запису ігноруємо.
 */
export async function markContact(channel: ContactChannel, ok: boolean): Promise<void> {
  try {
    await db.meta.put({ key: contactKey(channel, ok), value: new Date().toISOString() })
  } catch {
    // IndexedDB недоступна: просто не покажемо час.
  }
}
