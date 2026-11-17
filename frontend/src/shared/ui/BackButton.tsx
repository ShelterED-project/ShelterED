import { useNavigate } from 'react-router'

type Props = {
  /** Куди йти, якщо назад нікуди (сторінку відкрили за посиланням чи з закладки) */
  fallback?: string
  label?: string
  className?: string
}

/**
 * Стрілка «Назад»: на попередню сторінку застосунку, а якщо її немає — на fallback.
 * React Router зберігає номер запису історії в history.state.idx (0 — перша сторінка сеансу).
 */
export default function BackButton({ fallback = '/', label = 'Назад', className = '' }: Props) {
  const navigate = useNavigate()

  function goBack() {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0
    if (idx > 0) void navigate(-1)
    else void navigate(fallback)
  }

  return (
    <button
      type="button"
      onClick={goBack}
      className={`inline-flex h-11 items-center gap-2 rounded-[10px] pr-3 text-[15px] font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${className}`}
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M16 10H4M9 5L4 10L9 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </button>
  )
}
