/**
 * Маленький індикатор очікування всередині кнопки. Колір береться з тексту (currentColor).
 * Обертається лише якщо користувач не просив зменшити рух (енергоменеджер: мінімум анімацій).
 */
export default function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block size-4 shrink-0 rounded-full border-2 border-current border-r-transparent motion-safe:animate-spin ${className}`}
    />
  )
}
