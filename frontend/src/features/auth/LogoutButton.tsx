import { useLogout } from './useLogout'

/** Кнопка «Вийти». compact — лише іконка (мобільні шапки). */
export default function LogoutButton({ compact = false, className = '' }: { compact?: boolean; className?: string }) {
  const logout = useLogout()
  return (
    <button
      type="button"
      onClick={() => void logout()}
      aria-label={compact ? 'Вийти' : undefined}
      className={`flex items-center justify-center gap-2 text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${className}`}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <path d="m16 17 5-5-5-5" />
        <path d="M21 12H9" />
      </svg>
      {!compact && <span>Вийти</span>}
    </button>
  )
}
