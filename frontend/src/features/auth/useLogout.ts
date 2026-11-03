import { useNavigate } from 'react-router'
import { useAppDispatch, useAppSelector } from '@/app/hooks'
import { baseApi } from '@/shared/api/baseApi'
import { useLogoutMutation } from './authApi'
import { clearSession } from './session'

/** Вихід: локальну сесію чистимо одразу, відкликання токена на сервері — як вийде (може не бути мережі). */
export function useLogout() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const refreshToken = useAppSelector((s) => s.auth.session?.refreshToken)
  const [revoke] = useLogoutMutation()

  return async function logout() {
    // Спершу запит: після очищення сесії токена вже не буде. Не чекаємо відповіді.
    if (refreshToken) void revoke({ refresh_token: refreshToken }).unwrap().catch(() => undefined)
    await clearSession(dispatch)
    // Кеш запитів належить попередньому користувачу.
    dispatch(baseApi.util.resetApiState())
    navigate('/login', { replace: true })
  }
}
