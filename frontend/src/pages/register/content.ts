import iconAdmin from '@/assets/register/icon-role-admin.svg'
import iconStudent from '@/assets/register/icon-role-student.svg'
import iconTeacher from '@/assets/register/icon-role-teacher.svg'

export type Role = 'teacher' | 'admin' | 'student'

export const roleOptions: { value: Role; title: string; text: string; icon: string }[] = [
  { value: 'teacher', title: 'Вчитель', text: 'Створює клас і уроки', icon: iconTeacher },
  { value: 'admin', title: 'Адміністрація', text: 'Керує школою й класами', icon: iconAdmin },
  { value: 'student', title: 'Учень', text: 'Входить за кодом класу', icon: iconStudent },
]

// Тимчасовий список із макета: коли зʼявиться API шкіл, замінити на дані з нього.
export const schools = [{ id: 'lyceum-12-kharkiv', name: 'Ліцей №12, м. Харків' }]
