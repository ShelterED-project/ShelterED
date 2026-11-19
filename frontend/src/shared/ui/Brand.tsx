import { Link } from 'react-router'
import mole from '@/assets/landing/mole.svg'
import { homeByRole } from '@/features/auth/session'
import { useCurrentUser } from '@/features/auth/useCurrentUser'

export default function Brand({ size, collapsible = false }: { size: 'header' | 'footer' | 'app'; collapsible?: boolean }) {
  const user = useCurrentUser()
  // У кабінеті логотип не виводить на лендинг: веде на головну сторінку ролі користувача.
  const to = size === 'app' && user ? homeByRole[user.role] : '/'
  return (
    <Link to={to} aria-label={to === '/' ? 'ShelterED — на головну' : 'ShelterED — на головну кабінету'} className="flex shrink-0 items-center gap-2 rounded whitespace-nowrap">
      {/* У вузькому боковому меню напис прихований, тож знак бренду — кріт. */}
      {collapsible && <img src={mole} alt="" width={32} height={32} className="size-8 xl:hidden" />}
      <span className={`font-heading text-parchment ${size === 'header' ? 'text-lg md:text-2xl' : size === 'app' ? 'text-xl' : 'text-lg'}${collapsible ? ' max-xl:sr-only' : ''}`}>
        ShelterED
      </span>
    </Link>
  )
}
