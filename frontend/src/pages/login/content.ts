export type LoginRole = 'student' | 'teacher' | 'parent' | 'admin'

export const loginRoles: { value: LoginRole; label: string }[] = [
  { value: 'student', label: 'Учень' },
  { value: 'teacher', label: 'Вчитель' },
  { value: 'parent', label: 'Батьки' },
  { value: 'admin', label: 'Адміністрація' },
]
