import type { SchoolUser } from './adminApi'

type Named = Pick<SchoolUser, 'display_name' | 'last_name'>

export function userName(user: Named): string {
  return [user.display_name, user.last_name].filter(Boolean).join(' ')
}

export function userInitials(user: Named): string {
  return [user.display_name, user.last_name]
    .filter((part): part is string => Boolean(part))
    .map((part) => part[0].toUpperCase())
    .join('')
}

/** Поточний навчальний рік: з вересня — «2026/2027». */
export function currentAcademicYear(now = new Date()): string {
  const year = now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1
  return `${year}/${year + 1}`
}
