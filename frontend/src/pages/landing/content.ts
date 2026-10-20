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
  { href: '#roles', label: 'Для кого' },
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

export const roles = [
  {
    icon: studentIcon,
    title: 'Учням',
    text: 'Короткі модулі по 3–5 хвилин, тести без інтернету й Кріт, який пояснює іншими словами.',
    cta: 'Увійти учню',
    to: '/student',
  },
  {
    icon: teacherIcon,
    title: 'Вчителям',
    text: 'Готуйте уроки наперед, запускайте перекличку й бачте прогалини класу.',
    cta: 'Підключити клас',
    to: '/teacher',
  },
  {
    icon: schoolIcon,
    title: 'Адміністрації школи',
    text: 'Скільки дітей в укритті просто зараз, журнал тривог і керування класами.',
    cta: 'Для школи',
    to: '/admin',
  },
]

export const safety = [
  { icon: silentIcon, title: 'Тихий режим', text: 'Субтитри на всіх відео, усе можна пройти без звуку.' },
  { icon: batteryIcon, title: 'Береже заряд', text: 'Темна тема й мінімум анімацій за замовчуванням.' },
  { icon: shieldIcon, title: 'Безпека дітей', text: 'Жодної геолокації, мінімум даних, доступ за ролями.' },
  { icon: wifiIcon, title: 'Працює без мережі', text: 'Локальний сервер на ноутбуці вчителя роздає уроки по Wi-Fi.' },
]
