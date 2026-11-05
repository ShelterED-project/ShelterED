import iconBell from '@/assets/parent/nav-notifications.svg'

export default function BellButton() {
  return (
    <button
      type="button"
      aria-label="Сповіщення"
      className="relative flex size-11 shrink-0 items-center justify-center rounded-xl border border-line focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
    >
      <img src={iconBell} alt="" width={20} height={20} />
      <span className="absolute top-2 right-2 size-2 rounded-full bg-accent" />
    </button>
  )
}
