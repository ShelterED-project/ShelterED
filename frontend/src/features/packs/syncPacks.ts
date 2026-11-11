import { store } from '@/app/store'
import { authApi } from '@/features/auth/authApi'
import { saveSession } from '@/features/auth/session'
import { db } from '@/shared/db/db'
import { markContact } from '@/features/sync/contact'
import { packsApi } from './packsApi'

let running: Promise<void> | null = null

/** Клас учня. Сесії, збережені до появи class_id в /auth/me, дістають його одним запитом. */
async function resolveClassId(): Promise<string | null> {
  const { session, persisted } = store.getState().auth
  if (!session || session.user.role !== 'student') return null
  if (session.user.class_id !== undefined) return session.user.class_id

  const me = await store.dispatch(authApi.endpoints.me.initiate(undefined, { forceRefetch: true, subscribe: false }))
  if (!('data' in me) || !me.data) return null
  await saveSession(store.dispatch, { ...session, user: me.data }, persisted)
  return me.data.class_id ?? null
}

async function sync() {
  const classId = await resolveClassId()
  if (!classId) return

  const manifest = await store.dispatch(
    packsApi.endpoints.packManifest.initiate(classId, { forceRefetch: true, subscribe: false }),
  )
  // Без мережі лишаємо те, що вже збережено: урок має відкриватися з локальних даних.
  if (!('data' in manifest) || !manifest.data) {
    await markContact('packs', false)
    return
  }
  await markContact('packs', true)

  // Пакети іншого класу (інший учень на цьому пристрої) і минулі дні більше не потрібні.
  await db.packs.where('class_id').notEqual(classId).delete()
  await db.packs.where('pack_date').below(manifest.data.date_from).delete()

  const known = new Map((await db.packs.toArray()).map((pack) => [pack.id, pack.content_hash]))
  for (const item of manifest.data.packs) {
    if (known.get(item.id) === item.content_hash) continue
    const result = await store.dispatch(
      packsApi.endpoints.pack.initiate(item.id, { forceRefetch: true, subscribe: false }),
    )
    // Помилку одного пакета не вважаємо фатальною: решту докачуємо, цей повторимо при наступному запуску.
    if ('data' in result && result.data) await db.packs.put(result.data)
  }
}

/** Докачує змінені пакети «Рюкзака». Паралельні виклики ділять один запуск, помилки мережі тихі. */
export function requestPackSync(): Promise<void> {
  running ??= sync()
    .catch(() => undefined)
    .finally(() => {
      running = null
    })
  return running
}

/** Старт, повернення мережі, відкриття застосунку (iOS без Background Sync), вхід іншого користувача. */
export function startPackSync() {
  window.addEventListener('online', () => void requestPackSync())
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void requestPackSync()
  })

  let lastUserId = store.getState().auth.session?.user.id
  store.subscribe(() => {
    const userId = store.getState().auth.session?.user.id
    if (userId !== lastUserId) {
      lastUserId = userId
      if (userId) void requestPackSync()
    }
  })

  void requestPackSync()
}
