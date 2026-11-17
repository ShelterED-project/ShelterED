import { Link } from 'react-router'
import iconSettings from '@/assets/parent/nav-settings.svg'
import NavIcon from './NavIcon'

/** Шестерня в мобільній шапці: на телефоні бічного меню немає, а вихід живе в налаштуваннях. */
export default function SettingsLink({ to, className = '' }: { to: string; className?: string }) {
  return (
    <Link
      to={to}
      aria-label="Налаштування"
      className={`flex size-11 shrink-0 items-center justify-center rounded-xl border border-line text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${className}`}
    >
      <NavIcon src={iconSettings} size={20} />
    </Link>
  )
}
