import batteryIcon from '@/assets/landing/icon-battery.svg'
import schoolIcon from '@/assets/landing/icon-school.svg'
import shieldIcon from '@/assets/landing/icon-shield.svg'
import silentIcon from '@/assets/landing/icon-silent.svg'
import studentIcon from '@/assets/landing/icon-student.svg'
import teacherIcon from '@/assets/landing/icon-teacher.svg'
import wifiIcon from '@/assets/landing/icon-wifi.svg'
import type { FooterLink } from '@/shared/ui/SiteFooter'
import type { NavLink } from '@/shared/ui/SiteHeader'

export const headerLinks: NavLink[] = [
  { href: '#how', label: 'Як це працює' },
  { href: '#roles', label: 'Хто як входить' },
  { href: '#safety', label: 'Безпека' },
  { href: '#about', label: 'Про проєкт' },
]

export const footerLinks: FooterLink[] = [
  { href: '#how', label: 'Як це працює' },
  { label: 'Приватність' },
  { label: 'Екстрена допомога' },
  { label: 'Контакти' },
]

export const steps = [
  { title: 'Зранку, поки є світло', text: 'Пакет уроків на день завантажується автоматично.' },
  { title: 'Сирена посеред уроку', text: 'ShelterED знає розклад і відкриває матеріали саме цього уроку.' },
  { title: 'В укритті', text: 'Картки, тести й Кріт-провідник працюють без мережі.' },
  { title: 'Зв’язок повернувся', text: 'Прогрес і перекличка самі летять у хмару — без дублів.' },
]

/** Куди вести кожну роль: учні входять за кодом класу, дорослі — з поштою. */
export const signIn = {
  student: { to: '/register', label: 'Я учень — увійти' },
  adult: { to: '/login', label: 'Вчитель, батьки, школа — увійти' },
  hint: 'Учням не потрібна пошта: лише код класу від вчителя.',
  howLink: 'Хто як входить',
}

export const rolesSection = {
  title: 'Хто як входить',
  subtitle: 'Оберіть себе — і натисніть кнопку у своїй картці.',
  howTitle: 'Для входу потрібно',
}

export const roles = [
  {
    icon: studentIcon,
    title: 'Учням',
    text: 'Короткі модулі по 3–5 хвилин, тести без інтернету й Кріт, який пояснює іншими словами.',
    how: 'Код класу від вчителя, ім’я, прізвище й PIN. Пошта не потрібна.',
    cta: 'Увійти за кодом класу',
    to: signIn.student.to,
    primary: true,
  },
  {
    icon: teacherIcon,
    title: 'Вчителям',
    text: 'Готуйте уроки наперед, запускайте перекличку й бачте прогалини класу.',
    how: 'Пошта й пароль, які видала адміністрація школи.',
    cta: 'Увійти з поштою',
    to: signIn.adult.to,
  },
  {
    icon: shieldIcon,
    title: 'Батькам',
    text: 'Чи дитина в укритті під час тривоги, її прогрес і що варто повторити вдома.',
    how: 'Пошта й пароль від школи, а після входу — код дитини від класного керівника.',
    cta: 'Увійти з поштою',
    to: signIn.adult.to,
  },
  {
    icon: schoolIcon,
    title: 'Адміністрації школи',
    text: 'Скільки дітей в укритті просто зараз, журнал тривог і керування класами.',
    how: 'Пошта й пароль адміністратора школи.',
    cta: 'Увійти з поштою',
    to: signIn.adult.to,
  },
]

export const safety = [
  { icon: silentIcon, title: 'Тихий режим', text: 'Субтитри на всіх відео, усе можна пройти без звуку.' },
  { icon: batteryIcon, title: 'Береже заряд', text: 'Темна тема й мінімум анімацій за замовчуванням.' },
  { icon: shieldIcon, title: 'Безпека дітей', text: 'Жодної геолокації, мінімум даних, доступ за ролями.' },
  { icon: wifiIcon, title: 'Працює без мережі', text: 'Локальний сервер на ноутбуці вчителя роздає уроки по Wi-Fi.' },
]
