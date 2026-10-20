export type LoginRole = 'student' | 'teacher' | 'admin'

export const loginRoles: { value: LoginRole; label: string }[] = [
  { value: 'student', label: 'Учень' },
  { value: 'teacher', label: 'Вчитель' },
  { value: 'admin', label: 'Адміністрація' },
]
