import { db } from '@/shared/db/db'
import { sessionCleared, sessionSet } from './authSlice'
import type { Session } from './authSlice'
import type { Role, TokenResponse, User } from './types'

interface Dispatch {
  (action: ReturnType<typeof sessionSet> | ReturnType<typeof sessionCleared>): unknown
}

export function sessionFromTokens(tokens: TokenResponse, user: User): Session {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    expiresAt: Date.now() + tokens.expires_in * 1000,
    user,
  }
}

/** Головна сторінка ролі. */
export const homeByRole: Record<Role, string> = {
  student: '/student',
  teacher: '/teacher',
  parent: '/parent',
  admin: '/admin',
}

/** Кладе сесію в стор і, якщо persist, в IndexedDB (щоб пережити перезапуск без мережі). */
export async function saveSession(dispatch: Dispatch, session: Session, persist: boolean) {
  dispatch(sessionSet({ session, persisted: persist }))
  try {
    if (persist) await db.session.put({ id: 'current', ...session })
    else await db.session.clear()
  } catch {
    // IndexedDB недоступна (приватний режим): сесія лишається лише в памʼяті.
  }
}

export async function clearSession(dispatch: Dispatch) {
  dispatch(sessionCleared())
  try {
    await db.session.clear()
  } catch {
    // Нічого чистити, якщо сховища немає.
  }
}

/** Викликається при старті: піднімає збережену сесію зі сховища, без мережі. */
export async function restoreSession(dispatch: Dispatch) {
  try {
    const stored = await db.session.get('current')
    if (stored) {
      const { id: _id, ...session } = stored
      dispatch(sessionSet({ session: session as Session, persisted: true }))
    }
  } catch {
    // IndexedDB недоступна: працюємо без збереженого входу.
  }
}
