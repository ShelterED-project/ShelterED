import { Navigate, Outlet } from 'react-router'
import { useAppSelector } from '@/app/hooks'
import { homeByRole } from './session'

/**
 * Охоронець сторінок входу: користувача з активною сесією веде на головну його ролі, щоб на
 * тому самому пристрої не увійти «поверх» чужої сесії. Сесія — зі стору, тож працює без мережі.
 */
export default function RequireGuest() {
  const user = useAppSelector((s) => s.auth.session?.user)
  if (user) return <Navigate to={homeByRole[user.role]} replace />
  return <Outlet />
}
