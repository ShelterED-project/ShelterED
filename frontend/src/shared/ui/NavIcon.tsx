/**
 * Іконка навігації кольору тексту (currentColor). Файли SVG мають зашитий колір, тому малюємо
 * їх маскою: активний пункт і його іконка підсвічуються разом. Підходить лише для одноколірних іконок.
 */
export default function NavIcon({ src, size }: { src: string; size: number }) {
  const mask = `url("${src}") center / contain no-repeat`
  return (
    <span
      aria-hidden="true"
      className="inline-block shrink-0 bg-current"
      style={{ width: size, height: size, mask, WebkitMask: mask }}
    />
  )
}
