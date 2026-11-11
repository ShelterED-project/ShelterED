/**
 * Маленький індикатор очікування. Колір береться з тексту (currentColor).
 * Обертається лише якщо користувач не просив зменшити рух (енергоменеджер: мінімум анімацій).
 * large — для лоадера сторінки чи блоку, за замовчуванням розмір для кнопки.
 */
export default function Spinner({ className = '', large = false }: { className?: string; large?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block shrink-0 rounded-full border-2 border-current border-r-transparent motion-safe:animate-spin ${
        large ? 'size-6' : 'size-4'
      } ${className}`}
    />
  )
}
