import { Navigate, Outlet } from 'react-router'
import { useAppSelector } from '@/app/hooks'
import { homeByRole } from './session'
import type { Role } from './types'

/**
 * Охоронець маршруту: пускає лише вказані ролі. Читає сесію зі стору (вона піднята з IndexedDB
 * при старті), тому працює без мережі. Справжній захист даних робить бекенд.
 */
export default function RequireRole({ roles }: { roles: Role[] }) {
  const user = useAppSelector((s) => s.auth.session?.user)
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role)) return <Navigate to={homeByRole[user.role]} replace />
  return <Outlet />
}
