import { useAppSelector } from '@/app/hooks'

/** Поточний користувач зі збереженої сесії (працює без мережі). */
export function useCurrentUser() {
  const user = useAppSelector((s) => s.auth.session?.user)
  if (!user) return null
  const fullName = [user.display_name, user.last_name].filter(Boolean).join(' ')
  const initials = [user.display_name, user.last_name]
    .filter((part): part is string => Boolean(part))
    .map((part) => part[0].toUpperCase())
    .join('')
  return { ...user, fullName, initials }
}
